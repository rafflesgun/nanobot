# Nanobot Web UI

Standalone dashboard for multiple nanobot instances.

## MVP Requirements

- Each nanobot instance must expose the gateway admin API with `gateway.admin.enabled=true` and a non-empty `gateway.admin.token`.
- Each nanobot instance must enable the WebSocket channel for chat with a non-empty `channels.websocket.token`.
- The webui stores dashboard auth, admin tokens, and WebSocket tokens server-side only.

## Config File

The webui is configured from a mounted JSON config file. This keeps dashboard auth, per-instance URLs, ports, and tokens together instead of spreading secrets across long environment variable lists.

Set `WEBUI_CONFIG` to the mounted path:

```text
PORT=6060
WEBUI_CONFIG=/config/webui.config.json
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

| Field | Description |
|---|---|
| `authToken` | Browser dashboard bearer token |
| `instances[].id` | Stable instance id used by API routes and chat events |
| `instances[].name` | Display name; defaults to `id` when omitted |
| `instances[].adminBaseUrl` | Nanobot gateway/admin API base URL, including host and port |
| `instances[].adminToken` | Nanobot `gateway.admin.token` for admin API calls |
| `instances[].websocketUrl` | Base nanobot WebSocket endpoint, including host, port, and optional path |
| `instances[].websocketToken` | Nanobot `channels.websocket.token` for chat connections |
| `instances[].enabled` | Whether the webui should allow proxy/chat access; defaults to `true` |

Only `PORT` and `WEBUI_CONFIG` are read from environment variables. Instance URLs and tokens must come from the config file.

`websocketUrl` is the base nanobot WebSocket endpoint. The webui appends `client_id=nanobot-webui` and the configured `websocketToken` server-side. Do not include secrets in browser URLs.

## Docker Compose

Copy `webui.config.example.json` to `webui.config.json`, edit tokens and URLs, then run:

```bash
docker compose -f docker-compose.example.yml up --build
```

The compose example mounts `./webui.config.json` read-only at `/config/webui.config.json` and points `WEBUI_CONFIG` at that path.

Mount `/data` as a persistent volume. Current releases reserve it for dashboard-owned state; upcoming topic/history/instance CRUD storage will rely on it.

## Development

```bash
npm install
npm test
npm run dev:server
```

## Security Notes

- Do not expose this dashboard publicly without HTTPS and a strong dashboard token.
- The browser cannot choose arbitrary upstream URLs.
- Dashboard auth, nanobot admin tokens, and nanobot WebSocket tokens live in the mounted config file and stay server-side.
- Nanobot admin tokens are injected by the webui backend for admin API calls and are not returned by `/api/instances`.
- Nanobot WebSocket tokens are injected by the webui backend for chat connections and are not returned by `/api/instances`.
