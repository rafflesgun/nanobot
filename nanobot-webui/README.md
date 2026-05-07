# Nanobot Web UI

Standalone dashboard for multiple nanobot instances.

## MVP Requirements

- Each nanobot instance must expose the gateway admin API with `gateway.admin.enabled=true` and a non-empty `gateway.admin.token`.
- Each nanobot instance must enable the WebSocket channel for chat with a non-empty `channels.websocket.token`.
- The webui stores dashboard auth, admin tokens, and WebSocket tokens server-side only.

## Config File

The recommended deployment mode is a mounted JSON config file. This keeps per-instance URLs, ports, and tokens together instead of spreading them across long environment variables.

Set `WEBUI_CONFIG` to the mounted path:

```text
PORT=6060
WEBUI_CONFIG=/data/config.json
```

Example `config.json`:

```json
{
  "authToken": "dashboard-secret",
  "instances": [
    {
      "id": "alpha",
      "name": "Alpha",
      "adminBaseUrl": "http://nanobot-alpha:18790",
      "adminToken": "alpha-admin-token",
      "websocketUrl": "ws://nanobot-alpha:8765/",
      "websocketToken": "alpha-ws-token",
      "enabled": true
    }
  ]
}
```

`AUTH_TOKEN` may still be set as an environment variable to override `authToken` from the file.

## Environment Fallback

For quick demos, the webui can still be configured using environment variables only.

| Variable | Description |
|---|---|
| `PORT` | Webui HTTP port, default `6060` |
| `AUTH_TOKEN` | Browser dashboard bearer token; overrides config-file `authToken` |
| `WEBUI_CONFIG` | Path to mounted JSON config file |
| `NANOBOT_INSTANCES` | Comma-separated `id=url` admin gateway entries |
| `NANOBOT_INSTANCE_TOKENS` | Comma-separated `id=token` admin API tokens matching instances |
| `NANOBOT_INSTANCE_WEBSOCKET_TOKENS` | Comma-separated `id=token` WebSocket channel tokens matching instances; env fallback derives WebSocket URLs from admin host and port `8765` |

Environment-only example:

```text
AUTH_TOKEN=dashboard-secret
NANOBOT_INSTANCES=alpha=http://nanobot-alpha:18790,beta=http://nanobot-beta:18790
NANOBOT_INSTANCE_TOKENS=alpha=alpha-admin-token,beta=beta-admin-token
NANOBOT_INSTANCE_WEBSOCKET_TOKENS=alpha=alpha-ws-token,beta=beta-ws-token
```

## Docker Compose

Copy `webui.config.example.json` to `webui.config.json`, edit tokens and URLs, then run:

```bash
docker compose -f docker-compose.example.yml up --build
```

The compose example mounts `./webui.config.json` read-only at `/data/config.json`.

## Development

```bash
npm install
npm test
npm run dev:server
```

## Security Notes

- Do not expose this dashboard publicly without HTTPS and a strong dashboard token.
- The browser cannot choose arbitrary upstream URLs.
- Dashboard auth, nanobot admin tokens, and nanobot WebSocket tokens can all live in the mounted config file and stay server-side.
- Nanobot admin tokens are injected by the webui backend for admin API calls and are not returned by `/api/instances`.
- Nanobot WebSocket tokens are injected by the webui backend for chat connections and are not returned by `/api/instances`.
