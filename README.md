# sip-bridge

## Overview

sip-bridge is a lightweight bridge that listens to a specified ntfy topic and triggers actions when a message arrives. By default, it integrates with Asterisk/FreePBX to originate a call to a SIP extension (line 0) for high priority messages (priority >= 4).

### Features

- Connects to an ntfy topic via Server-Sent Events (SSE).
- For messages with priority ≥ 4 (high or max), initiates a call to a configured SIP extension via Asterisk AMI.
- **Optional HTTP webhook**: In addition to SIP calls, you can configure a `WEBHOOK_URL` to send an HTTP POST request containing the ntfy message for high priority alerts.
- Configurable via environment variables for easy deployment in Docker.

## Usage

### Deployment

The repository includes a Dockerfile and docker-compose.yml for quick deployment. To run the bridge:

```
docker compose up --build -d
```

Adjust the environment variables in `docker-compose.yml` to suit your environment. At minimum, you'll need:

- `NTFY_URL` – Base URL of your ntfy server (e.g. `https://ntfy.sh` or your self-hosted instance).
- `NTFY_TOPIC` – Topic name to subscribe to.
- `AMI_*` variables – Host, port, username and password for Asterisk AMI access.
- `EXTENSION`, `CHANNEL_TECH`, `DIAL_STRING` – SIP extension/endpoint to call.
- `CALLERID` – Caller ID to show on the phone.

### Webhook Support

To enable webhook notifications, set the environment variable `WEBHOOK_URL` to the URL you want to call when a high priority alert is received. When set, the bridge will send a JSON payload via HTTP POST to the specified `WEBHOOK_URL` containing the ntfy message, including title, message body, and priority.

Example `docker-compose.yml` snippet:

```yaml
services:
  ntfy-to-sip:
    environment:
      WEBHOOK_URL: "https://example.com/hook"  # Replace with your webhook endpoint
```

The JSON payload has the following structure:

```json
{
  "title": "Smoke Alarm",
  "message": "Smoke detected in server room",
  "priority": 4
}
```

### Running outside Docker

You can run the script directly after installing dependencies:

```
pip install aiohttp
python ntfy_to_sip.py
```

Ensure the required environment variables are set or create a `.env` file.

## Contributing

Pull requests are welcome! Feel free to open issues or suggest improvements.

## License

This project is released under the MIT License.
