# WebUI Complete Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved complete dashboard shell, fix remaining light cards, and format chat streams into readable transcript messages.

**Architecture:** Keep the browser-to-webui auth boundary unchanged. Add small focused client utilities/components: a transcript reducer for protocol events, topic state inside `ChatPanel`, a local instance CRUD shell, and a `ManagePanel` that composes existing settings/logs panels with unsupported placeholders for missing admin APIs.

**Tech Stack:** Vue 3 `<script setup>`, TypeScript, Vitest, Vue Test Utils, Koa, Socket.IO.

---

## File Structure

- Create `nanobot-webui/src/client/chatTranscript.ts`: pure reducer for user-visible transcript entries and raw debug events.
- Create `nanobot-webui/src/client/chatTranscript.test.ts`: TDD coverage for delta aggregation, ignored terminal events, errors, and outbound entries.
- Modify `nanobot-webui/src/client/components/ChatPanel.vue`: topic sidebar, formatted transcript, debug drawer, dark styles.
- Modify `nanobot-webui/src/client/components/ChatPanel.test.ts`: topic UI and formatted transcript tests.
- Create `nanobot-webui/src/client/components/InstancesPanel.vue`: local instance CRUD shell with dark forms/cards.
- Create `nanobot-webui/src/client/components/InstancesPanel.test.ts`: create/edit/disable/delete behavior and no secret rendering.
- Create `nanobot-webui/src/client/components/ManagePanel.vue`: selected target instance and subnav for Settings/Subagents/Logs/Usage/Costing/Session/Memory/Restart.
- Create `nanobot-webui/src/client/components/ManagePanel.test.ts`: subnav, target selection, existing panel reuse, unsupported states.
- Modify `nanobot-webui/src/client/App.vue`: primary nav becomes Overview/Chat Topics/Instances/Manage.
- Modify `nanobot-webui/src/client/App.test.ts`: verifies approved nav shape and Manage subnav access.
- Modify `nanobot-webui/src/client/components/OverviewPanel.vue`, `LogsPanel.vue`, `SettingsPanel.vue`: replace bright surfaces with dark surfaces.
- Create `nanobot-webui/src/client/theme.test.ts`: guard against bright panel backgrounds in authenticated components.

## Tasks

### Task 1: Chat Transcript Reducer

- [ ] Write failing tests in `chatTranscript.test.ts` for merging two `delta` chunks into one assistant entry, ignoring `stream_end` and `turn_end`, adding outbound user messages, and preserving raw debug events.
- [ ] Run `npm test -- src/client/chatTranscript.test.ts`; expect failures because the module does not exist.
- [ ] Implement `chatTranscript.ts` with `createTranscriptState`, `applyChatEvent`, and `appendOutboundMessage`.
- [ ] Run `npm test -- src/client/chatTranscript.test.ts`; expect pass.
- [ ] Commit `feat(webui): format chat protocol events`.

### Task 2: Chat Topics UI

- [ ] Add failing tests to `ChatPanel.test.ts` for topic creation, topic switching, formatted delta transcript, hidden terminal events, and debug drawer raw events.
- [ ] Run `npm test -- src/client/components/ChatPanel.test.ts`; expect failures.
- [ ] Update `ChatPanel.vue` to use `chatTranscript.ts`, add session-local topics, selected instances per topic, and dark chat layout.
- [ ] Run `npm test -- src/client/components/ChatPanel.test.ts src/client/chatTranscript.test.ts`; expect pass.
- [ ] Commit `feat(webui): add topic chat transcript UI`.

### Task 3: Instances CRUD Shell

- [ ] Create failing `InstancesPanel.test.ts` for create, edit, disable, delete, and secret redaction.
- [ ] Run `npm test -- src/client/components/InstancesPanel.test.ts`; expect failure.
- [ ] Implement `InstancesPanel.vue` with local browser-state CRUD and dark surfaces.
- [ ] Run `npm test -- src/client/components/InstancesPanel.test.ts`; expect pass.
- [ ] Commit `feat(webui): add instance management shell`.

### Task 4: Manage Subnav Shell

- [ ] Create failing `ManagePanel.test.ts` for target instance selector, subnav labels, Settings/Logs reuse, and unsupported placeholders.
- [ ] Run `npm test -- src/client/components/ManagePanel.test.ts`; expect failure.
- [ ] Implement `ManagePanel.vue` composing `SettingsPanel`, `LogsPanel`, and dark unsupported panels.
- [ ] Run `npm test -- src/client/components/ManagePanel.test.ts`; expect pass.
- [ ] Commit `feat(webui): add manage subnav shell`.

### Task 5: App Navigation And Dark Surface Guard

- [ ] Add failing App tests for primary nav `Overview`, `Chat Topics`, `Instances`, `Manage`, and no top-level `Logs`/`Settings`.
- [ ] Add failing `theme.test.ts` that scans dashboard Vue files for bright surface declarations like `background: #fbfdff`, `background: #fff;`, and `border: 1px solid #dce4ef`.
- [ ] Run `npm test -- src/client/App.test.ts src/client/theme.test.ts`; expect failures.
- [ ] Update `App.vue` nav and replace bright styles in existing panels.
- [ ] Run `npm test -- src/client/App.test.ts src/client/theme.test.ts src/client/components/OverviewPanel.test.ts src/client/components/LogsPanel.test.ts src/client/components/SettingsPanel.test.ts`; expect pass.
- [ ] Commit `feat(webui): complete dark dashboard navigation`.

### Task 6: Full Verification

- [ ] Run `npm test && npm run build && docker compose -f docker-compose.example.yml config && npx tsc -p tsconfig.server.json --noEmit && npx tsc --noEmit` from `nanobot-webui`; expect exit 0.
- [ ] Run `docker build -t nanobot-webui:complete-shell-smoke . && docker run --rm nanobot-webui:complete-shell-smoke node -e "import('./dist/server/index.js').then(() => console.log('server import ok'))"`; expect `server import ok`.
- [ ] Run `git status --short --branch`; expect only intentional changes.

## Self-Review

- Spec coverage: tasks cover dark surfaces, chat formatting, topic shell, instance CRUD shell, Manage subnav, tests, and verification.
- Placeholder scan: placeholders are explicit unsupported UI states for missing backend APIs, not vague implementation gaps.
- Type consistency: transcript reducer types are introduced before `ChatPanel` uses them; panel names match App imports.
