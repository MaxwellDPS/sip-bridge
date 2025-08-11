#!/usr/bin/env python3
"""
Bridge ntfy alerts to a SIP device.

This script listens to a given ntfy topic via Server‑Sent Events (SSE). When a
message arrives with a priority of 4 or higher (ntfy priorities range from 1
for the lowest to 5 for the highest), it originates a call to a SIP device via
the Asterisk Manager Interface (AMI).  The call simply rings the configured
extension, drawing attention to the alert.

Usage: run this script in an environment with appropriate environment
variables (see below) or modify the defaults in the code.  A common setup is
to containerise this script alongside a PBX using Docker or Docker Compose.

Environment variables:

  NTFY_URL       – Base URL of your ntfy server (defaults to https://ntfy.sh).
  NTFY_TOPIC     – Topic to subscribe to for alerts (defaults to "alerts").
  NTFY_AUTH      – Optional Basic auth credentials for ntfy (format: user:pass).

  EXTENSION      – Extension to ring on the PBX (defaults to "1000").
  CALLERID       – Caller ID presented on the ringing phone.

  AMI_HOST       – Hostname or IP address of the Asterisk/FreePBX AMI.
  AMI_PORT       – Port of the AMI (defaults to 5038).
  AMI_USER       – AMI username with originate permissions.
  AMI_PASS       – AMI password.

  CHANNEL_TECH   – Channel technology (e.g. PJSIP or SIP).
  DIAL_STRING    – Dial string used to originate the call; defaults to
                   "{CHANNEL_TECH}/{EXTENSION}".

  CONTEXT        – Dialplan context to originate from (e.g. from‑internal).
  PRIORITY       – Priority within the context (usually 1).
  TIMEOUT_MS     – Ring timeout in milliseconds.

  LOG_LEVEL      – Logging level (INFO by default).

When the script detects a high‑priority alert, it connects to the AMI,
authenticates, and issues an Originate action. It then closes the AMI
connection. Errors during AMI connection or originate are logged but do not
crash the subscriber loop.
"""

import asyncio
import json
import logging
import os
import socket
from contextlib import asynccontextmanager

import aiohttp

# ---------------------------------------------------------------------------
# Configuration via environment variables with sane defaults
NTFY_URL = os.getenv("NTFY_URL", "https://ntfy.sh")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "alerts")
NTFY_AUTH = os.getenv("NTFY_AUTH", "")

EXTENSION = os.getenv("EXTENSION", "1000")
CALLERID = os.getenv("CALLERID", "NTFY Bridge <7777>")

AMI_HOST = os.getenv("AMI_HOST", "pbx")
AMI_PORT = int(os.getenv("AMI_PORT", "5038"))
AMI_USER = os.getenv("AMI_USER", "ntfybridge")
AMI_PASS = os.getenv("AMI_PASS", "secret")

CHANNEL_TECH = os.getenv("CHANNEL_TECH", "PJSIP")
DIAL_STRING = os.getenv("DIAL_STRING", f"{CHANNEL_TECH}/{EXTENSION}")

CONTEXT = os.getenv("CONTEXT", "from-internal")
PRIORITY = int(os.getenv("PRIORITY", "1"))
TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", "30000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s: %(message)s")

def _ami_line(cmd_dict: dict) -> bytes:
    """Format a dictionary of AMI key/values into CRLF-terminated bytes."""
    return ("\r\n".join(f"{k}: {v}" for k, v in cmd_dict.items()) + "\r\n\r\n").encode()

class AMIClient:
    """A minimal AMI client for issuing Originate actions."""
    def __init__(self, host: str, port: int, username: str, secret: str) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.secret = secret
        self.sock: socket.socket | None = None
    def connect(self) -> None:
        """Connect to the AMI and log in."""
        self.sock = socket.create_connection((self.host, self.port), timeout=10)
        _ = self.sock.recv(4096)
        self._send({
            "Action": "Login",
            "Username": self.username,
            "Secret": self.secret,
            "Events": "off",
        })
        response = self._read_until_blank()
        if b"Success" not in response:
            raise RuntimeError(f"AMI login failed: {response!r}")
    def close(self) -> None:
        """Send a logoff action and close the socket."""
        try:
            if self.sock:
                self._send({"Action": "Logoff"})
        except Exception:
            pass
        finally:
            if self.sock:
                try:
                    self.sock.close()
                finally:
                    self.sock = None
    def _send(self, cmd: dict) -> None:
        if not self.sock:
            raise RuntimeError("AMI connection not open")
        self.sock.sendall(_ami_line(cmd))
    def _read_until_blank(self) -> bytes:
        if not self.sock:
            raise RuntimeError("AMI connection not open")
        chunks: list[bytes] = []
        self.sock.settimeout(10)
        while True:
            data = self.sock.recv(4096)
            if not data:
                break
            chunks.append(data)
            if b"\r\n\r\n" in data:
                break
        return b"".join(chunks)
    def originate_simple(self, channel: str, exten: str, context: str, priority: int,
                          callerid: str, timeout_ms: int) -> None:
        action = {
            "Action": "Originate",
            "Channel": channel,
            "Context": context,
            "Exten": exten,
            "Priority": priority,
            "CallerID": callerid,
            "Timeout": timeout_ms,
            "Async": "true",
        }
        self._send(action)
        _ = self._read_until_blank()

@asynccontextmanager
async def ntfy_session():
    """Create an aiohttp ClientSession with optional basic auth."""
    headers = {}
    if NTFY_AUTH:
        import base64
        headers["Authorization"] = "Basic " + base64.b64encode(NTFY_AUTH.encode()).decode()
    async with aiohttp.ClientSession(headers=headers) as session:
        yield session

async def subscribe_ntfy() -> None:
    sse_url = f"{NTFY_URL.rstrip('/')}/{NTFY_TOPIC}/sse"
    logging.info(f"Subscribing to ntfy SSE: {sse_url}")
    async with ntfy_session() as session:
        async with session.get(sse_url, timeout=None) as resp:
            resp.raise_for_status()
            async for line in resp.content:
                try:
                    decoded = line.decode("utf-8", "ignore").strip()
                except Exception:
                    continue
                if not decoded.startswith("data: "):
                    continue
                payload = decoded[6:]
                try:
                    msg = json.loads(payload)
                except json.JSONDecodeError:
                    logging.debug(f"Ignoring non‑JSON payload: {payload[:120]}")
                    continue
                await handle_ntfy_msg(msg)

async def handle_ntfy_msg(msg: dict) -> None:
    prio = int(msg.get("priority", 3))
    title = msg.get("title", "")
    body = msg.get("message", "")
    logging.info(f"ntfy message: priority={prio} title={title!r} message={body!r}")
    if prio >= 4:
        logging.info("High priority detected; placing SIP call to line 0...")
        ami = AMIClient(AMI_HOST, AMI_PORT, AMI_USER, AMI_PASS)
        try:
            ami.connect()
            ami.originate_simple(
                channel=DIAL_STRING,
                exten=EXTENSION,
                context=CONTEXT,
                priority=PRIORITY,
                callerid=CALLERID,
                timeout_ms=TIMEOUT_MS,
            )
            logging.info("Originate sent via AMI.")
        except Exception as exc:
            logging.exception(f"AMI originate failed: {exc}")
        finally:
            try:
                ami.close()
            except Exception:
                pass
async def main() -> None:
    while True:
        try:
            await subscribe_ntfy()
        except aiohttp.ClientError as err:
            logging.warning(f"SSE connection error: {err}; retrying in 3 s...")
            await asyncio.sleep(3)
        except Exception as err:
            logging.exception(f"Unexpected error: {err}; retrying in 5 s...")
            await asyncio.sleep(5)
if __name__ == "__main__":
    asyncio.run(main())
