# sip-bridge

This project bridges ntfy topic messages to SIP phone calls and an optional HTTP webhook. It listens on an ntfy topic and, for high-priority messages (priority >= 4), it originates a call to a SIP extension on your PBX via Asterisk/FreePBX’s AMI. It can also forward the raw message to a configurable HTTP webhook.

## Features

- Subscribe to an ntfy topic via Server‑Sent Events (SSE).
- For messages with priority >= 4 (high or max), originate a call to a SIP device (line 0) via AMI.
- Optional JSON webhook: send the entire ntfy message to an HTTP endpoint for further processing.
- Docker friendly; all configuration is via environment variables in an `.env` file.

## Configuration

Copy `.sample.env` to `.env` and adjust values. When running with Docker Compose, variables from `.env` are loaded automatically via `env_file`.

| Variable | Description | Example/Default |
| --- | --- | --- |
| NTFY_URL | Base URL of your ntfy server. | https://ntfy.sh |
| NTFY_TOPIC | Topic to subscribe for alerts. | my-alerts |
| NTFY_AUTH | Basic auth for ntfy (`username:password`). Leave empty if not required. | (empty) |
| WEBHOOK_HOST | Hostname or IP of the HTTP webhook listener. Leave empty to disable. | (empty) |
| WEBHOOK_PORT | Port of the webhook listener. | 8080 |
| WEBHOOK_PATH | Path prefix for webhook POST (starting with `/`). | /hook |
| AMI_HOST | Host/IP of your FreePBX/Asterisk AMI. | pbx |
| AMI_PORT | AMI port number. | 5038 |
| AMI_USER | AMI username with originate rights. | ntfybridge |
| AMI_PASS | AMI password/secret. | secret |
| EXTENSION | Extension/line to ring for high alerts. | 1000 |
| CHANNEL_TECH | Channel technology (`PJSIP`, `SIP`, etc.). | PJSIP |
| DIAL_STRING | Dial string used in originate (often `${CHANNEL_TECH}/${EXTENSION}`). | PJSIP/1000 |
| CONTEXT | Dialplan context to originate from (often `from-internal` on FreePBX). | from-internal |
| PRIORITY | Dialplan priority for originate. | 1 |
| CALLERID | Caller ID used on the call. | NTFY Bridge <7777> |
| TIMEOUT_MS | Ring timeout in milliseconds. | 30000 |
| LOG_LEVEL | Python logging level. | INFO |

To enable the webhook, set `WEBHOOK_HOST`, `WEBHOOK_PORT`, and `WEBHOOK_PATH`. The script assembles `http://<WEBHOOK_HOST>:<WEBHOOK_PORT><WEBHOOK_PATH>` and sends the ntfy message as JSON via HTTP POST.

## Deployment

### Docker Compose

Use the provided `docker-compose.yml`:

```bash
cp .sample.env .env  # customise variables in .env
docker compose up --build -d
```

This builds the image locally and runs the service using your `.env` configuration.

### Manual (no Docker)

Install dependencies and run the script:

```bash
pip install aiohttp
export NTFY_URL=https://ntfy.sh
export NTFY_TOPIC=my-alerts
# export other variables as needed…
python ntfy_to_sip.py
```

## Testing

An end-to-end test is provided in `tests/test_send_webhook.py`. It starts a simple HTTP server and asserts that the `send_webhook` helper posts the correct payload. The GitHub Actions workflow runs these tests, builds the Docker image, and publishes it to the GitHub Container Registry (`ghcr.io/<owner>/sip-bridge`) on each push to `main`.

Run tests locally:

```bash
pip install aiohttp pytest
pytest -q
```

## License

MIT
