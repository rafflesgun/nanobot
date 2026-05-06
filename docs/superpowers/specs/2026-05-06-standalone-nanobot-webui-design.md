# Standalone Nanobot Web UI Design

Date: 2026-05-06

## Goal

Build a standalone `nanobot-webui` project and Docker container that can connect to multiple running nanobot instances, monitor them, and provide a browser dashboard for chat, sessions, settings, and logs. The first implementation slice is core dashboard functionality. Group chat, file browsing, analytics, and container lifecycle management come later.

## Context

Hermes Web UI provides a strong reference architecture: a Vue/Vite frontend, a Koa backend-for-frontend, dashboard auth, explicit API routes, upstream proxying, Socket.IO for long-running interactions, logs, settings, and group chat state. Its implementation is tightly coupled to Hermes profiles, local Hermes CLI access, shared Hermes home directories, and local gateway lifecycle management.

Nanobot currently has these relevant surfaces:

- A WebSocket channel with streaming chat, multi-chat multiplexing, media handling, and embedded WebUI REST endpoints.
- An OpenAI-compatible HTTP API with `/v1/chat/completions`, `/v1/models`, and `/health`.
- A gateway health endpoint that only reports `{"status":"ok"}`.
- Session storage through `SessionManager`.
- Minimal embedded WebUI settings endpoints for model/provider display and update.

These existing surfaces are not enough for a standalone multi-instance dashboard. The standalone webui needs a stable admin contract from each nanobot instance.

## Decisions

- Project shape: standalone `nanobot-webui` project/container.
- First slice: core dashboard first.
- Nanobot changes are allowed: add a versioned admin API to each nanobot instance.
- Discovery: static instance configuration in the webui container.
- Auth: single dashboard auth; webui stores per-instance admin tokens server-side.
- Chat transport: require each nanobot instance to enable its WebSocket channel.
- Integration boundary: network APIs only. Do not mount nanobot workspaces or config directories into the webui container for MVP.

## Architecture

The standalone webui is a separate service that talks to nanobot instances over the Docker network or another configured network. The browser talks only to the webui backend.

```text
Browser
  |
  | HTTP / Socket.IO / WebSocket
  v
nanobot-webui container
  |
  | authenticated server-side proxy/admin calls
  v
nanobot-a container    nanobot-b container    nanobot-c container
  |                    |                      |
  | admin API          | admin API            | admin API
  | websocket chat     | websocket chat       | websocket chat
```

The webui owns:

- Dashboard authentication.
- Static instance registry parsing.
- Per-instance admin tokens, kept server-side only.
- Health polling and status aggregation.
- Browser-facing APIs.
- WebSocket or Socket.IO bridge between browser and nanobot WebSocket channel.
- Dashboard-owned persistence in `/data`.
- Later group-chat rooms, messages, agent membership, and orchestration state.

Each nanobot instance owns:

- Its runtime, workspace, sessions, providers, channels, and logs.
- A new authenticated `/admin/v1` API.
- Its existing WebSocket channel for chat streaming.
- Config validation and persistence.

## Standalone Webui Components

### Frontend

Use Vue 3, TypeScript, and Vite. Hermes Web UI can be used as a structural reference, but nanobot-specific code should be namespaced under `nanobot/`, not `hermes/`.

MVP views:

- `Instances`: list configured nanobot instances, health, model/provider, enabled transports, and last error.
- `Chat`: select an instance, create or attach websocket chats, stream replies, display `stream_end` and `turn_end` state.
- `Sessions`: list, filter, read, and delete sessions exposed by the nanobot admin API.
- `Settings`: display and update basic model/provider settings.
- `Logs`: list and read/tail approved logs exposed by the nanobot admin API.

### Backend-For-Frontend

Use Koa if adapting Hermes Web UI directly. The BFF serves the SPA, enforces dashboard auth, loads static instance config, polls health, proxies authenticated admin requests, bridges chat traffic, and writes webui-owned state under `/data`.

The BFF must never expose per-instance nanobot admin tokens to browser code.

### Webui Persistence

Use SQLite in `/data/nanobot-webui.db`.

MVP tables:

- `instances_cache`: latest health/status snapshot for configured instances.
- `ui_settings`: selected default instance and display settings.
- `audit_events`: config changes, failed dashboard auth, failed upstream calls, and security-relevant errors.

Future tables:

- `group_rooms`
- `group_messages`
- `group_room_agents`
- `group_context_snapshots`

## Nanobot Admin API

Add a real HTTP admin API under `/admin/v1`. This should not be implemented through the current `websockets` `process_request` shim because admin features need proper HTTP verbs, request bodies, pagination, and durable auth semantics.

Authentication:

- Require `Authorization: Bearer <admin_token>`.
- The admin token is configured per nanobot instance.
- Missing or invalid tokens return `401` or `403`.
- Tokens are never returned by admin endpoints.

MVP endpoints:

- `GET /admin/v1/status`
- `GET /admin/v1/sessions`
- `GET /admin/v1/sessions/{key}/messages`
- `DELETE /admin/v1/sessions/{key}`
- `GET /admin/v1/settings`
- `PATCH /admin/v1/settings`
- `GET /admin/v1/logs`
- `GET /admin/v1/logs/{name}`

Status response should include browser-safe fields such as version, uptime if available, model/provider summary, enabled channels/transports, websocket availability, workspace/config identifiers as appropriate, and last known degraded state. Sensitive paths or secrets must be redacted or omitted.

Session APIs should expose all supported session types, not only `websocket:` sessions. Support filters and pagination:

```http
GET /admin/v1/sessions?channel=websocket&limit=50&cursor=...
```

Settings MVP should focus on model/provider display and updates. Nanobot owns validation, config persistence, and `requires_restart` reporting.

Logs APIs should list only approved log files and support bounded tail reads. Log streaming can be added later.

## Instance Configuration

For MVP, instances are configured statically in the webui container via environment variables or an equivalent config file.

Example:

```text
NANOBOT_INSTANCES=alpha=http://nanobot-alpha:18790,beta=http://nanobot-beta:18790
NANOBOT_INSTANCE_TOKENS=alpha=...,beta=...
```

The BFF normalizes this into:

```ts
type NanobotInstance = {
  id: string
  name: string
  baseUrl: string
  adminToken: string
  enabled: boolean
}
```

The browser can select configured instance IDs only. It cannot supply arbitrary upstream URLs.

## Docker Shape

Example MVP deployment:

```yaml
services:
  nanobot-webui:
    image: nanobot-webui
    ports:
      - "6060:6060"
    volumes:
      - nanobot-webui-data:/data
    environment:
      - PORT=6060
      - AUTH_TOKEN=change-me
      - NANOBOT_INSTANCES=alpha=http://nanobot-alpha:18790,beta=http://nanobot-beta:18790
      - NANOBOT_INSTANCE_TOKENS=alpha=alpha-token,beta=beta-token

  nanobot-alpha:
    image: nanobot
    expose:
      - "18790"
      - "8765"

  nanobot-beta:
    image: nanobot
    expose:
      - "18790"
      - "8765"

volumes:
  nanobot-webui-data:
```

The webui container should not mount the Docker socket for MVP. Docker-label discovery and container lifecycle controls are later features.

## Data Flows

### Instance Health

On startup and periodically afterward, the BFF calls:

```http
GET /admin/v1/status
Authorization: Bearer <instance-token>
```

The BFF caches latest status and exposes a token-redacted browser API:

```http
GET /api/instances
```

Failures are scoped per instance. One offline instance must not affect others.

### Chat

The browser sends chat actions to the webui BFF with an `instanceId` and optional `chatId`. The BFF opens or reuses a server-side connection to the selected nanobot WebSocket endpoint, then relays normalized events to the browser.

Browser-to-BFF events include `instanceId`, `chatId`, content, and media metadata. BFF-to-browser events always include `instanceId` and `chatId` so one browser tab can track multiple instances and chats.

Nanobot WebSocket events to preserve:

- `ready`
- `attached`
- `delta`
- `stream_end`
- `turn_end`
- `message`
- `error`

For MVP, if the browser disconnects, the BFF can close the upstream nanobot WebSocket to keep state simple. Reconnect preservation can be added later.

### Sessions

Browser route:

```http
GET /api/instances/{instanceId}/sessions
GET /api/instances/{instanceId}/sessions/{key}/messages
DELETE /api/instances/{instanceId}/sessions/{key}
```

BFF forwards to the selected nanobot admin API with the configured token. Nanobot redacts raw local filesystem paths and returns signed or safe media references where needed.

### Settings

Browser route:

```http
GET /api/instances/{instanceId}/settings
PATCH /api/instances/{instanceId}/settings
```

The BFF forwards to nanobot. Nanobot validates and persists. If a change requires restart, nanobot returns `requires_restart: true`; the webui displays it but does not restart containers in MVP.

### Logs

Browser route:

```http
GET /api/instances/{instanceId}/logs
GET /api/instances/{instanceId}/logs/{name}?tail=500
```

BFF forwards to nanobot. Nanobot restricts readable logs to approved log files and enforces bounded reads.

## Error Handling

Instance and upstream errors are scoped per instance.

- Offline instance: show `offline`, preserve other instances.
- `401/403`: show `Auth failed` for that instance.
- `404`: show `Unsupported feature` or `Admin API unavailable`.
- `5xx`: show a safe upstream error and record details in webui logs/audit.
- Timeout: show a per-instance timeout state.
- WebSocket connection failure: emit `chat.connection_failed` with `instanceId`.
- WebSocket disconnect mid-run: emit `chat.disconnected` with `instanceId` and `chatId`.
- Config validation failures: return and display field-level errors.

Security controls:

- Browser never receives nanobot instance tokens.
- Browser cannot select arbitrary upstream URLs.
- BFF strips browser `Authorization` before forwarding and injects configured instance credentials.
- Dashboard auth failures and config mutations are written to `audit_events`.

## Testing

### Nanobot Tests

- Admin auth rejects missing and invalid tokens.
- `GET /admin/v1/status` returns browser-safe version/model/provider/channel fields.
- Session listing includes supported non-websocket sessions and supports filters/pagination.
- Session messages redact unsafe paths and media references cannot escape media roots.
- Settings patch validates model/provider and persists through the existing config loader.
- Logs endpoints list only approved logs and enforce bounded tail reads.

### Webui Server Tests

- Static instance config parsing handles malformed, missing, and duplicate entries.
- `/api/instances` redacts tokens.
- Admin proxy injects configured instance token and strips browser auth.
- Unknown instance IDs return `404`.
- Upstream timeout/down cases produce scoped errors.
- WebSocket bridge relays nanobot `delta`, `stream_end`, `turn_end`, and `message` with `instanceId`.

### Frontend Tests

- Instance list renders online, offline, auth-failed, and unsupported-feature states.
- Chat event routing keys on `instanceId + chatId`.
- Session list filters by instance.
- Settings form handles validation errors and `requires_restart`.
- Auth flow stores only the dashboard token.

### Integration Tests

- Run the webui against two fake nanobot upstreams.
- Verify one offline instance does not break the other.
- Verify the browser cannot call arbitrary upstreams.
- Verify independent chat flows against `alpha` and `beta`.

## MVP Scope

In scope:

- New standalone `nanobot-webui` project/container.
- Single dashboard auth.
- Static instance config.
- Per-instance health/status.
- Required nanobot WebSocket chat transport.
- Webui BFF bridge/proxy so browser never talks directly to nanobot.
- Versioned nanobot admin API for status, sessions, basic settings, and logs.
- Basic Docker Compose example.

Out of scope:

- Docker socket discovery.
- Start/stop/restart nanobot containers.
- Direct config volume editing.
- Full provider credential management.
- Multi-user roles.
- Terminal into containers.
- Full Hermes-style group chat orchestration.
- File browser.
- Usage/cost analytics unless nanobot already exposes enough usage data.

## Future Group Chat

Group chat should be phase 2 after the instance manager and websocket bridge are stable. Group chat state belongs to the webui database, not to individual nanobot instances.

Room agents should point to:

```ts
type RoomAgent = {
  roomId: string
  instanceId: string
  agentName: string
  displayName: string
  persona?: string
}
```

The BFF will orchestrate multi-agent turns through each instance's chat/admin APIs. Mention routing should resolve both target room agent and target nanobot instance. Context compression and room summaries are later additions.
