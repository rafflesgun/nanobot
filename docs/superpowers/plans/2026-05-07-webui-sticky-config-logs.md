# WebUI Sticky Config Logs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix dashboard layout alignment and add config/log editor modes plus visible webui runtime logs.

**Architecture:** Keep existing Vue/Koa architecture. Make shell/layout changes in `App.vue`, settings/log viewer changes in their components, and webui runtime logging as a small focused server module used by `createApp`.

**Tech Stack:** Vue 3, TypeScript, Koa, Vitest, Vue Test Utils.

---

## Tasks

### Task 1: Sticky Floating Shell Layout

- [ ] Add failing App tests for `floating-header`, `main-body`, `sidebar-panel`, `content-scroll`, and top-aligned `content-stage` hooks.
- [ ] Run `npm test -- src/client/App.test.ts`; expect failure.
- [ ] Update `App.vue` shell CSS/classes to mirror the reference behavior: fixed header, full-height app shell, glass sidebar, content scroll, no centering.
- [ ] Run `npm test -- src/client/App.test.ts`; expect pass.
- [ ] Commit `feat(webui): add sticky dashboard shell layout`.

### Task 2: Settings GUI JSON Markdown Modes

- [ ] Add failing `SettingsPanel.test.ts` coverage for mode tabs, JSON editor content, markdown summary, invalid JSON error, and aligned toolbar.
- [ ] Run `npm test -- src/client/components/SettingsPanel.test.ts`; expect failure.
- [ ] Implement settings modes in `SettingsPanel.vue` without adding dependencies.
- [ ] Run `npm test -- src/client/components/SettingsPanel.test.ts`; expect pass.
- [ ] Commit `feat(webui): add settings editor modes`.

### Task 3: Logs Filter And Raw View

- [ ] Add failing `LogsPanel.test.ts` coverage for filter input, formatted/raw toggle, and toolbar alignment.
- [ ] Run `npm test -- src/client/components/LogsPanel.test.ts`; expect failure.
- [ ] Implement filter/raw modes in `LogsPanel.vue`.
- [ ] Run `npm test -- src/client/components/LogsPanel.test.ts`; expect pass.
- [ ] Commit `feat(webui): add log viewer modes`.

### Task 4: WebUI Runtime Logs

- [ ] Add failing server tests for authenticated `/api/webui/logs`, unauthorized rejection, and request log collection.
- [ ] Run `npm test -- src/server/index.test.ts`; expect failure.
- [ ] Create `src/server/webuiLogger.ts` and wire it into `createApp`.
- [ ] Add client API helper and minimal LogsPanel source option for WebUI Runtime if feasible.
- [ ] Run `npm test -- src/server/index.test.ts src/client/api.test.ts src/client/components/LogsPanel.test.ts`; expect pass.
- [ ] Commit `feat(webui): expose runtime logs`.

### Task 5: Full Verification

- [ ] Run `npm test && npm run build && docker compose -f docker-compose.example.yml config && npx tsc -p tsconfig.server.json --noEmit && npx tsc --noEmit`.
- [ ] Run Docker smoke import.
- [ ] Merge locally after verification.

## Self-Review

- Spec coverage: layout, settings modes, logs modes, and webui runtime logs are mapped to tasks.
- Placeholder scan: no unresolved placeholders.
- Type consistency: mode names and test hook names are consistent across tasks.
