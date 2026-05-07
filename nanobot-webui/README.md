# Nanobot Web UI

Standalone dashboard for multiple nanobot instances.

## MVP Requirements

- Each nanobot instance must expose the gateway admin API with `gateway.admin.enabled=true` and a non-empty `gateway.admin.token`.
- Each nanobot instance must enable the WebSocket channel for chat with a non-empty `channels.websocket.token`.
- The webui stores dashboard auth, admin tokens, and WebSocket tokens server-side only.

## Environment

| Variable | Description |
|---|---|
| `PORT` | Webui HTTP port, default `6060` |
| `AUTH_TOKEN` | Browser dashboard bearer token |
| `NANOBOT_INSTANCES` | Comma-separated `id=url` entries |
| `NANOBOT_INSTANCE_TOKENS` | Comma-separated `id=token` admin API tokens matching instances |
| `NANOBOT_INSTANCE_WEBSOCKET_TOKENS` | Comma-separated `id=token` WebSocket channel tokens matching instances |

Example:

```text
AUTH_TOKEN=dashboard-secret
NANOBOT_INSTANCES=alpha=http://nanobot-alpha:18790,beta=http://nanobot-beta:18790
NANOBOT_INSTANCE_TOKENS=alpha=alpha-admin-token,beta=beta-admin-token
NANOBOT_INSTANCE_WEBSOCKET_TOKENS=alpha=alpha-ws-token,beta=beta-ws-token
```

## Development

```bash
npm install
npm test
npm run dev:server
```

## Security Notes

- Do not expose this dashboard publicly without HTTPS and a strong `AUTH_TOKEN`.
- The browser cannot choose arbitrary upstream URLs.
- Nanobot admin tokens are injected by the webui backend for admin API calls and are not returned by `/api/instances`.
- Nanobot WebSocket tokens are injected by the webui backend for chat connections and are not returned by `/api/instances`.
