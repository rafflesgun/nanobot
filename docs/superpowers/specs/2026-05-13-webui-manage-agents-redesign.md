# Manage Agents Page Redesign

**Date**: 2026-05-13
**Status**: Approved

## Summary

Redesign the Agents and Manage Agents tabs to support proper CRUD with GUI/JSON toggle, remote agent config via JSON CodeMirror editor, subagent Markdown editing, and a restart button. Keep two separate tabs (Approach B) — "Agents" for instance CRUD, "Manage Agents" for per-agent configuration.

## Architecture

Two tabs remain in the nav sidebar:

1. **Agents** — instance connection CRUD with GUI Form / JSON editor toggle
2. **Manage Agents** — per-agent configuration with instance sidebar + sub-section tabs

### Agents Tab (InstancesPanel Enhancement)

- **GUI Form / JSON toggle** at the top of the form area
  - **GUI Form mode**: existing form fields (ID, Name, Base URL, Admin Token, WebSocket Token, Enabled toggle) — same fields as today, cleaner layout
  - **JSON mode**: CodeMirror 6 editor showing all instances as a JSON array, with JSON schema validation on save. Editing the JSON array updates all instances at once (bulk edit)
- Toggle persists for the session (not across page loads)
- JSON editor validates on save — invalid JSON shows inline error, save is blocked
- Instance cards on the right stay largely the same (edit/toggle/disable/delete)

### Manage Tab (ManagePanel Enhancement)

- Replace dropdown with **instance list sidebar** (left panel) — shows all enabled instances with status dots, click to select
- **Restart button** in the header area next to the selected instance name — always visible regardless of which sub-section is active
- Sub-nav tabs: **Agent Config** | **Subagents** | **Logs**
- Remove "Settings" tab (replaced by Agent Config)
- Remove unsupported placeholder tabs (Session, Memory, Credentials)

#### Agent Config Tab

- CodeMirror 6 in JSON mode
- Fetches `InstanceSettings` from the agent, displays raw JSON
- Saves via `PATCH /settings` — extracts `model` + `provider` from parsed JSON `agent` key
- Read-only metadata below editor: resolved_provider, has_api_key, requires_restart
- Invalid JSON or missing `agent.model`/`agent.provider` blocks save with inline error

#### Subagents Tab

- List of subagents loaded from `fetchSubagents()`
- Click "Edit" opens CodeMirror 6 in Markdown mode for that subagent's content
- Save via `saveSubagent()`, delete via `deleteSubagent()`
- "New Subagent" button at top

#### Logs Tab

- Unchanged from current LogsPanel

#### Restart Button

- Placed in the header area next to instance name, always visible
- Calls `POST /api/instances/:id/restart` (new endpoint — currently unsupported, shows "coming soon" toast until backend adds it)

### CodeEditor.vue (Shared Component)

Reusable component wrapping CodeMirror 6:

- **Props**: `modelValue` (string), `language` (`'json' | 'markdown'`), `readOnly` (boolean), `placeholder` (string)
- **Emits**: `update:modelValue` for v-model binding
- **JSON mode features**: syntax highlighting, bracket matching, line numbers, lint/validation via `@codemirror/lang-json` + `@codemirror/lint`. Invalid JSON gets red gutter marks + inline error messages. `isValid` ref exposed for parent to block save.
- **Markdown mode features**: syntax highlighting via `@codemirror/lang-markdown`, line numbers
- **Shared**: dark theme matching the oklch color system, consistent styling with existing textarea dimensions
- **Packages**: `codemirror` + `@codemirror/lang-json` + `@codemirror/lang-markdown` + `@codemirror/lint` + `@codemirror/theme-one-dark` (as base, customized)

## Data Flow

### Agents Tab

- **GUI Form → save**: Same as current — builds `StateInstance` object, calls `saveStateInstances()`
- **JSON → save**: Parse JSON array from CodeMirror, validate each entry has required fields (`id`, `name`, `baseUrl`), call `saveStateInstances()` with the parsed array. Invalid JSON or missing required fields → show error, block save.
- **Loading instances into JSON editor**: Serialize current `localInstances` to formatted JSON array on mode switch to JSON
- **Sync**: When JSON editor saves successfully, update `localInstances` ref from the response so GUI form and cards stay in sync

### Manage Tab

- **Instance sidebar**: Uses `instances` prop (from App.vue), filters to `enabled` only. Clicking sets `selectedInstanceId`.
- **Agent Config tab**: Fetch via `fetchInstanceSettings()` → serialize to JSON → CodeMirror. Save: parse JSON, extract `model` + `provider` from `agent` key, call `patchInstanceSettings()`. Show validation errors if JSON is invalid or `agent.model`/`agent.provider` missing.
- **Subagents tab**: Fetch list via `fetchSubagents()`. Edit: fetch single via `fetchSubagent()`, load content into CodeMirror Markdown. Save via `saveSubagent()`. Delete via `deleteSubagent()`.
- **Restart button**: Calls `POST /api/instances/:id/restart` (new endpoint, graceful degradation until backend implements)
- **Logs tab**: Unchanged, uses `fetchInstanceLogs()` + `fetchLogTail()`

## Navigation Changes

- Sidebar nav: "Agents" (unchanged) + "Manage Agents" (unchanged label, enhanced content)
- Remove the old "Manage Agents" sub-nav sections: Settings, Session, Memory, Credentials, Restart
- New Manage Agents sub-nav: Agent Config, Subagents, Logs

## Files to Modify/Create

- `nanobot-webui/src/client/components/InstancesPanel.vue` — add GUI/JSON toggle, CodeMirror JSON editor
- `nanobot-webui/src/client/components/ManagePanel.vue` — replace dropdown with instance sidebar, new sub-nav tabs, restart button
- `nanobot-webui/src/client/components/SettingsPanel.vue` — replace textarea with CodeEditor.vue, remove markdown mode
- `nanobot-webui/src/client/components/SubagentsPanel.vue` — replace textarea with CodeEditor.vue in markdown mode
- `nanobot-webui/src/client/components/CodeEditor.vue` — new shared CodeMirror 6 wrapper
- `nanobot-webui/src/client/components/InstancesPanel.test.ts` — update for JSON toggle
- `nanobot-webui/src/client/components/ManagePanel.test.ts` — update for new layout
- `nanobot-webui/src/client/components/CodeEditor.test.ts` — new tests for shared component
- `package.json` — add codemirror dependencies

## Out of Scope

- Session management tab (requires nanobot session API)
- Memory management tab (requires nanobot memory API)
- Credential management tab (requires nanobot credentials API)
- Live restart status polling (backend endpoint not yet available)
- CodeMirror autocompletion for agent config JSON schema
- Subagent template scaffolding (future)
