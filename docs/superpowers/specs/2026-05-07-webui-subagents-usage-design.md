# WebUI Subagents and Usage Design

## Goal

Activate the next dashboard slice by adding real subagent management and token usage/costing visibility.

Usage belongs on the main dashboard Overview as gauges/cards/charts with an instance switcher. Subagents belong under `Manage > Subagents` as a concise list with edit/delete actions and a Markdown editor for workspace agent definitions.

## Scope

In scope:

- Add nanobot admin APIs for subagent list/read/create/update/delete.
- Add nanobot admin API for token usage summaries from `workspace/stats/usage.jsonl`.
- Add webui BFF proxy endpoints for subagents and usage per configured instance.
- Add Overview usage cards/gauges/charts, defaulting to the first enabled instance.
- Activate `Manage > Subagents` with list, edit icon action, delete action, and Markdown editor.
- Keep built-in subagents visible but read-only.
- Keep workspace subagents editable and deletable.
- Treat `Costing` as token accounting only in this slice; no currency estimates.

Out of scope:

- Running or testing subagents from the dashboard.
- Editing built-in `nanobot/agents/*.md` files.
- Model pricing tables, currency conversion, billing-provider integrations, budgets, alerts, or invoices.
- Docker/container lifecycle controls.
- Arbitrary workspace file browsing.

## Visual Direction

Use `docs/superpowers/nanobot-dashboard-dark-layout.html` as the layout and style baseline for this slice.

The new UI should be dark, compact, and dashboard-like:

- Usage appears as main Overview metrics, not only in the Manage section.
- Usage totals use card/gauge/chip treatments with zero-state values when no data exists.
- Trend and breakdown charts should be simple and readable without adding a charting dependency unless the codebase already has one.
- Subagents use a clean list/table with name, description, model, source badge, edit icon button, and delete button.
- Editing a subagent opens a Markdown editor panel or drawer adjacent to the list. It should not replace the whole Manage shell.

## Subagent Admin API

Nanobot exposes authenticated admin endpoints under `/admin/v1`:

- `GET /admin/v1/subagents`
- `GET /admin/v1/subagents/{name}`
- `PUT /admin/v1/subagents/{name}`
- `DELETE /admin/v1/subagents/{name}`

Response item shape:

```json
{
  "name": "release-reviewer",
  "description": "Reviews release notes before merge",
  "model": "anthropic/claude-sonnet-4-5",
  "tools": ["read_file", "grep"],
  "max_iterations": 6,
  "max_tokens": 8000,
  "source": "workspace",
  "editable": true
}
```

`source` is either `builtin` or `workspace`.

`GET /admin/v1/subagents/{name}` returns the same metadata plus `content`, the full markdown file content.

`PUT /admin/v1/subagents/{name}` accepts:

```json
{ "content": "---\nname: release-reviewer\ndescription: ...\n---\n\nPrompt body" }
```

The server validates the content before writing:

- frontmatter parses as YAML when present
- effective `name` matches the URL name
- description is a string when present
- model is a string when present
- tools is a list of strings when present
- max iteration/token values are numeric when present
- prompt body is non-empty after frontmatter

`DELETE` removes only workspace agents. Built-in agents return a safe error such as `403 read-only subagent`.

## Subagent File Safety

Only workspace `agents/*.md` files are writable.

Names must be slug-like:

- lower/upper ASCII letters
- digits
- dash or underscore
- no slashes
- no dots
- no null bytes
- no empty names

The admin server resolves all write/delete targets under `ctx.config.workspace_path / "agents"`, checks the resolved path is still inside that directory, and writes only `{name}.md`.

Built-in files from `nanobot/agents/*.md` can be listed and read. They cannot be modified or deleted.

If a workspace agent has the same name as a built-in agent, the workspace agent shadows the built-in and is editable as a workspace agent. Listing returns one item for that name with `source: "workspace"`.

## Subagents WebUI

`ManagePanel` activates the existing `subagents` section.

The panel includes:

- target instance inherited from the Manage target selector
- refresh action
- `New subagent` action
- list rows with name, description, model, source badge, edit icon button, and delete button
- Markdown editor for selected workspace subagent
- read-only Markdown viewer for built-in subagents

Edit behavior:

- Clicking the edit icon loads `GET /subagents/{name}` through the webui BFF.
- Workspace agents open an editable Markdown textarea.
- Built-in agents open a read-only Markdown viewer with save/delete disabled.
- Save uses `PUT` and then refreshes the list.
- Delete asks for confirmation in the UI and then calls `DELETE` only for workspace agents.

Create behavior:

- `New subagent` starts a new draft with starter frontmatter.
- The user provides a safe name field and Markdown content.
- Save validates and writes it as a workspace subagent.

No run/test button is included in this slice.

## Usage Admin API

Nanobot exposes:

- `GET /admin/v1/usage`

Optional query parameters:

- `days`: integer, default `30`, min `1`, max `366`
- `channel`: optional exact channel filter
- `session_key`: optional exact session key filter
- `model`: optional exact model filter

The endpoint reads `ctx.config.workspace_path / "stats" / "usage.jsonl"` using existing usage records produced by `StatsManager.record_usage()`.

If the file does not exist, the response is a zero-state payload, not an error.

Response shape:

```json
{
  "range": { "days": 30 },
  "totals": {
    "count": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
    "cached_tokens": 0
  },
  "by_day": [],
  "by_model": [],
  "by_channel": [],
  "by_session": [],
  "pricing": {
    "configured": false,
    "message": "Pricing is not configured; showing token usage only."
  }
}
```

Breakdown rows include at least:

```json
{
  "key": "anthropic/claude-sonnet-4-5",
  "count": 12,
  "input_tokens": 1000,
  "output_tokens": 250,
  "total_tokens": 1250,
  "cached_tokens": 400
}
```

The endpoint ignores malformed JSONL lines and includes a `warnings` array when lines are skipped. Warnings should not include file paths or raw line contents.

## Usage / Costing WebUI

Usage is primarily shown in `OverviewPanel`.

Behavior:

- Default selected instance is the first enabled instance.
- The user can switch usage instance from a compact selector in Overview.
- Disabled instances are not selected by default.
- If no enabled instance exists, Overview shows usage cards with zero values and a short “No enabled instance selected” message.
- If the selected instance has no usage data, cards and chart remain flat at zero.
- Fetch errors show a non-sensitive inline warning while preserving the zero cards.

Overview usage widgets:

- total tokens card/gauge
- input tokens card
- output tokens card
- cached tokens card
- call/message count card
- simple daily token trend chart
- breakdown table by model or channel

`Manage > Usage` and `Manage > Costing` no longer show unsupported placeholders. In this slice they render a compact focused token-accounting view that reuses the same API and zero-state behavior as Overview. `Manage > Costing` displays token totals plus the pricing-not-configured message; it does not estimate currency.

Currency cost handling:

- no currency estimates are calculated
- no model pricing is embedded
- costing UI says `Pricing is not configured; showing token usage only`
- API returns `pricing.configured: false`

## WebUI BFF API

The browser never talks directly to nanobot admin endpoints.

The webui server adds authenticated routes such as:

- `GET /api/instances/:id/subagents`
- `GET /api/instances/:id/subagents/:name`
- `PUT /api/instances/:id/subagents/:name`
- `DELETE /api/instances/:id/subagents/:name`
- `GET /api/instances/:id/usage?days=30`

These proxy to the configured instance using the server-side admin token. Responses must not include admin tokens, upstream URLs beyond already-public `baseUrl`, or filesystem paths.

## Error Handling

Subagents:

- unknown instance: `404`
- disabled instance: `400` or safe error in webui panel
- invalid name: `400 invalid subagent name`
- invalid markdown/frontmatter: `400` with field-specific message
- built-in edit/delete: `403 read-only subagent`
- missing workspace agent on delete: safe not-found response

Usage:

- missing usage file: zero-state payload
- malformed JSONL lines: skip and add warning count
- invalid `days`: clamp numeric values into `1..366`; non-numeric values use the default `30`
- unreachable instance: webui shows zero cards plus inline warning

## Tests

Nanobot admin tests:

- subagent endpoints require admin auth
- list includes built-ins as read-only
- workspace subagent shadows built-in and is editable
- read returns markdown content without filesystem paths
- put creates a valid workspace agent
- put rejects unsafe names and invalid frontmatter
- delete removes workspace agent
- delete rejects built-in agent
- usage endpoint returns zero payload when usage file is absent
- usage endpoint aggregates totals by day/model/channel/session
- usage endpoint skips malformed lines with safe warning

WebUI server tests:

- subagent proxy endpoints require dashboard auth
- usage proxy endpoint requires dashboard auth
- proxy uses configured instance IDs only
- proxy responses do not expose admin tokens
- disabled or unknown instances return safe errors

WebUI component tests:

- Overview defaults usage selector to first enabled instance
- Overview renders zero cards when no usage data exists
- Overview reloads usage when switching instances
- Overview renders daily trend and model/channel breakdown
- Subagents panel lists name, description, model, source badge
- edit icon opens Markdown editor
- built-in editor is read-only and cannot save/delete
- workspace editor can save
- workspace delete action removes the item after confirmation

Verification:

- `npm test`
- `npm run build`
- `npx tsc -p tsconfig.server.json --noEmit`
- `npx tsc --noEmit`
- `docker compose -f docker-compose.example.yml config`
- Docker smoke import for `nanobot-webui`
- Python admin tests with `python3 -m pytest tests/admin ...`
