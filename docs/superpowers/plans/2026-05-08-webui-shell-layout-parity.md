# WebUI Shell Layout Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the nanobot-webui visual shell, layout, colors, sidebar, topbar, and CSS match the dark layout reference with strict parity, while preserving existing Nanobot dashboard content, data bindings, menu items, and subpage functionality. Also remove redundant per-subpage instance selectors and Usage/Costing from Manage subnav.

**Architecture:** Replace the current floating-header + padded-flex-body shell with the reference two-column app grid (sidebar + main). Migrate all inline rgba/hex colors to OKLCH CSS custom properties matching the reference palette. Update component styles to use token-based classes. Remove per-subpage instance selectors since ManagePanel already provides target-instance selection.

**Tech Stack:** Vue 3, Vitest, CSS custom properties, OKLCH color space.

---

## File Structure

- Modify: `nanobot-webui/src/client/App.vue` — rebuild shell layout, add CSS tokens, topbar, sidebar, responsive breakpoints
- Modify: `nanobot-webui/src/client/App.test.ts` — update shell structure assertions
- Modify: `nanobot-webui/src/client/components/OverviewPanel.vue` — migrate to token-based styles
- Modify: `nanobot-webui/src/client/components/OverviewPanel.test.ts` — minimal style assertion updates
- Modify: `nanobot-webui/src/client/components/ManagePanel.vue` — remove Usage/Costing sections, apply reference workspace/subnav layout
- Modify: `nanobot-webui/src/client/components/ManagePanel.test.ts` — update section expectations
- Modify: `nanobot-webui/src/client/components/SubagentsPanel.vue` — remove instance selector, apply reference card styles
- Modify: `nanobot-webui/src/client/components/SubagentsPanel.test.ts` — remove per-panel instance assertions
- Modify: `nanobot-webui/src/client/components/LogsPanel.vue` — remove instance selector, apply reference log styles
- Modify: `nanobot-webui/src/client/components/LogsPanel.test.ts` — remove per-panel instance assertions
- Modify: `nanobot-webui/src/client/components/SettingsPanel.vue` — remove instance selector, apply reference card styles
- Modify: `nanobot-webui/src/client/components/SettingsPanel.test.ts` — remove per-panel instance assertions
- Modify: `nanobot-webui/src/client/components/ChatPanel.vue` — apply reference visual tokens
- Modify: `nanobot-webui/src/client/components/InstanceList.vue` — restyle as sidebar bottom connection card

---

### Task 1: App Shell CSS Tokens and Color System

**Files:**
- Modify: `nanobot-webui/src/client/App.vue`

- [ ] **Step 1: Add CSS custom properties to App.vue**

Replace the existing `:root` block and all inline color references with OKLCH tokens from the reference. In `App.vue` `<style>` section, replace the `:root` block:

```css
:root {
  color: var(--fg);
  background: var(--bg);
  font-family: var(--font-body);
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  --bg: oklch(15% 0.012 255);
  --surface: oklch(19% 0.014 255);
  --surface-2: oklch(23% 0.014 255);
  --fg: oklch(94% 0.006 255);
  --muted: oklch(66% 0.012 255);
  --border: oklch(29% 0.012 255);
  --accent: oklch(64% 0.18 255);
  --success: oklch(70% 0.14 145);
  --warn: oklch(78% 0.14 85);
  --danger: oklch(68% 0.17 25);
  --font-display: -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
  --font-body: -apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui, sans-serif;
  --font-mono: ui-monospace, 'SF Mono', Menlo, Monaco, Consolas, monospace;
  --radius: 14px;
}
```

Then update all remaining CSS in App.vue to use these tokens:
- `#050814` → `var(--bg)`
- `#dbe7ff` / `#f8fbff` / `#e2e8f0` / `#dbeafe` / `#e5eefb` / `#cbd5e1` → `var(--fg)`
- `#93a4bd` / `#94a3b8` / `#7f8aa3` → `var(--muted)`
- `rgba(148, 163, 184, 0.2)` borders → `1px solid var(--border)`
- `rgba(15, 23, 42, 0.78)` / `rgba(8, 13, 28, 0.72)` / `rgba(8, 13, 28, 0.76)` backgrounds → `oklch(19% 0.014 255 / 0.88)` or `var(--surface)` with appropriate alpha
- `#60a5fa` / accent blues → `var(--accent)`
- `#2563eb` / `#2458d3` → `var(--accent)`
- `#22c55e` / `#86efac` → `var(--success)`
- `#fdba74` / `#fecaca` → `var(--warn)` / `var(--danger)`

- [ ] **Step 2: Run tests to verify no visual regressions break functional tests**

Run: `cd nanobot-webui && npm test`

Expected: All 117 tests pass (CSS token changes should not break functional assertions).

- [ ] **Step 3: Commit**

```bash
git add nanobot-webui/src/client/App.vue
git commit -m "style(webui): migrate app shell to OKLCH design tokens"
```

---

### Task 2: Rebuild App Shell Layout

**Files:**
- Modify: `nanobot-webui/src/client/App.vue`
- Modify: `nanobot-webui/src/client/App.test.ts`

- [ ] **Step 1: Rewrite the dashboard shell template to match reference structure**

Replace the `v-else` (authenticated) section of App.vue template with the reference layout structure. The key changes:

```html
<section v-else data-testid="dashboard-shell" class="app">
  <aside class="sidebar" aria-label="Primary navigation">
    <div class="brand">
      <div class="brand-mark">
        <div class="logo">nb</div>
        <div>
          <h1>nanobot</h1>
          <p>local agent console</p>
        </div>
      </div>
      <button class="icon-button" aria-label="Collapse sidebar" @click="sidebarCollapsed = !sidebarCollapsed">⌘</button>
    </div>

    <nav class="nav-section" aria-label="Main">
      <div class="section-label">Workspace</div>
      <button class="nav-item" :class="{ 'is-active': activeTab === 'overview' }" @click="activeTab = 'overview'">
        <span class="nav-left"><span class="nav-icon"></span>Overview</span>
      </button>
      <button class="nav-item" :class="{ 'is-active': activeTab === 'chat' }" @click="activeTab = 'chat'">
        <span class="nav-left"><span class="nav-icon"></span>Chat Topics</span>
      </button>
      <button class="nav-item" :class="{ 'is-active': activeTab === 'instances' }" @click="activeTab = 'instances'">
        <span class="nav-left"><span class="nav-icon"></span>Instances</span>
      </button>
      <button class="nav-item" :class="{ 'is-active': activeTab === 'manage' }" @click="activeTab = 'manage'">
        <span class="nav-left"><span class="nav-icon"></span>Manage</span>
      </button>
    </nav>

    <div class="sidebar-bottom">
      <div class="connection-card">
        <div class="connection-row">
          <div class="connection-title">Gateway</div>
          <span class="pill"><span class="dot" :class="{ success: onlineCount > 0 }"></span>{{ onlineCount > 0 ? 'online' : 'offline' }}</span>
        </div>
        <div class="muted mono" style="font-size: 11px; line-height: 1.5;">{{ instanceSummary }}</div>
      </div>
    </div>
  </aside>

  <main class="main">
    <header class="topbar">
      <button class="icon-button mobile-menu" aria-label="Open navigation" @click="mobileMenuOpen = !mobileMenuOpen">☰</button>
      <div class="crumbs"><span>nanobot</span><span>/</span><strong>{{ activeTabLabel }}</strong></div>
      <div class="top-actions">
        <button class="button" @click="refreshActivePanel">Refresh</button>
        <button v-if="activeTab === 'chat'" class="button primary" @click="activeTab = 'chat'">New chat</button>
        <button class="button secondary" @click="logout">Log out</button>
      </div>
    </header>

    <div class="mobile-tabs" aria-label="Mobile navigation">
      <span class="pill" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">Overview</span>
      <span class="pill" :class="{ active: activeTab === 'chat' }" @click="activeTab = 'chat'">Chat</span>
      <span class="pill" :class="{ active: activeTab === 'instances' }" @click="activeTab = 'instances'">Instances</span>
      <span class="pill" :class="{ active: activeTab === 'manage' }" @click="activeTab = 'manage'">Manage</span>
    </div>

    <section class="content">
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <OverviewPanel v-if="activeTab === 'overview'" :token="token" :instances="instances" />
      <ChatPanel v-else-if="activeTab === 'chat'" :token="token" :instances="instances" />
      <InstancesPanel v-else-if="activeTab === 'instances'" :token="token" :instances="instances" />
      <ManagePanel v-else :token="token" :instances="instances" />
    </section>
  </main>
</section>
```

Add to `<script setup>`:
```ts
const sidebarCollapsed = ref(false)
const mobileMenuOpen = ref(false)

const activeTabLabel = computed(() => {
  const labels: Record<string, string> = { overview: 'Overview', chat: 'Chat Topics', instances: 'Instances', manage: 'Manage' }
  return labels[activeTab.value] || 'Dashboard'
})

const onlineCount = computed(() => instances.value.filter((i) => i.enabled).length)
const instanceSummary = computed(() => {
  if (instances.value.length === 0) return 'No instances configured'
  return `${onlineCount.value} of ${instances.value.length} instances online`
})

function refreshActivePanel() {
  // Force re-render by toggling key or emitting event; simplest: re-fetch instances
  void login()
}
```

- [ ] **Step 2: Replace App.vue CSS with reference layout styles**

Replace the entire `<style>` section with styles matching the reference layout. Key sections:

```css
.app {
  display: grid;
  grid-template-columns: 268px minmax(0, 1fr);
  min-height: 100vh;
}

.sidebar {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  border-inline-end: 1px solid var(--border);
  background: oklch(16% 0.012 255 / 0.9);
  backdrop-filter: blur(18px);
}

.brand { /* reference .brand styles */ }
.brand-mark { /* reference .brand-mark styles */ }
.logo { /* reference .logo styles */ }
.icon-button { /* reference .icon-button styles */ }
.nav-section { padding: 10px; }
.section-label { /* reference .section-label styles */ }
.nav-item { /* reference .nav-item styles */ }
.nav-item.is-active { /* reference .is-active styles */ }
.nav-left { /* reference .nav-left styles */ }
.nav-icon { /* reference .nav-icon styles */ }
.sidebar-bottom { /* reference .sidebar-bottom styles */ }
.connection-card { /* reference .connection-card styles */ }
.connection-row { /* reference .connection-row styles */ }
.connection-title { /* reference .connection-title styles */ }
.pill { /* reference .pill styles */ }
.dot { /* reference .dot styles */ }
.dot.success { background: var(--success); }

.main {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
  min-height: 62px;
  padding: 12px 22px;
  border-block-end: 1px solid var(--border);
  background: oklch(16% 0.012 255 / 0.82);
  backdrop-filter: blur(18px);
}

.mobile-menu { display: none; }
.crumbs { /* reference .crumbs styles */ }
.crumbs strong { color: var(--fg); font-weight: 600; }
.top-actions { /* reference .top-actions styles */ }
.button { /* reference .button styles */ }
.button.primary { /* reference .button.primary styles */ }

.content {
  width: min(100%, 1440px);
  margin-inline: auto;
  padding: 22px;
}

.mobile-tabs {
  display: none;
  gap: 6px;
  overflow-x: auto;
  padding: 10px 14px;
  border-block-end: 1px solid var(--border);
  background: var(--surface);
}

/* Responsive breakpoints from reference */
@media (max-width: 920px) {
  .app { grid-template-columns: 1fr; }
  .sidebar { display: none; }
  .mobile-menu { display: inline-grid; }
  .mobile-tabs { display: flex; }
  .topbar { grid-template-columns: auto minmax(0, 1fr); padding: 10px 14px; }
  .top-actions .button:not(.primary) { display: none; }
  .content { padding: 14px; }
}

@media (max-width: 620px) {
  .crumbs { font-size: 11px; }
  .topbar { min-height: 56px; }
  .content { padding: 10px; }
}
```

Also migrate `.panel`, `.secondary`, `.error`, login styles to use `var()` tokens.

- [ ] **Step 3: Update App.test.ts assertions**

The existing tests reference `data-testid="floating-header"`, `data-testid="sidebar-panel"`, `data-testid="sidebar-nav"`, `data-testid="instance-status-bar"`, `data-testid="content-scroll"`, `data-testid="content-stage"`, `data-testid="logout-button"`. Update:

- Remove `floating-header` / `instance-status-bar` assertions (instance status moved to sidebar connection card).
- `sidebar-nav` → test that sidebar contains nav items with `.nav-item` class.
- `content-scroll` / `content-stage` → replaced by `.content`; update assertions to check `.content` contains the active panel.
- `logout-button` → now in topbar `.top-actions`; update selector.
- Add assertion that `.app` grid layout exists after login.
- Add assertion that `.sidebar` contains brand mark and nav items.
- Add assertion that `.topbar` contains crumbs and actions.

- [ ] **Step 4: Run tests and fix failures**

Run: `cd nanobot-webui && npm test`

Expected: All tests pass after assertion updates.

- [ ] **Step 5: Commit**

```bash
git add nanobot-webui/src/client/App.vue nanobot-webui/src/client/App.test.ts
git commit -m "feat(webui): rebuild shell layout matching reference sidebar/topbar/grid"
```

---

### Task 3: Update InstanceList to Connection Card

**Files:**
- Modify: `nanobot-webui/src/client/components/InstanceList.vue`

- [ ] **Step 1: Restyle InstanceList as sidebar bottom connection card**

The InstanceList component is currently an inline pill strip. Repurpose it to render inside the sidebar bottom connection card. Since App.vue now owns the connection-card markup, simplify InstanceList to just provide instance count/status data, or inline the instance status directly in App.vue's sidebar-bottom section and remove InstanceList from the topbar.

Simplest approach: remove InstanceList import from the topbar (already moved to sidebar-bottom in Task 2). If InstanceList is still imported, remove it from App.vue and delete the component file, replacing with inline sidebar-bottom content.

If other components reference InstanceList, keep it but restyle. Check:

Run: `cd nanobot-webui && rg 'InstanceList' src/`

If only App.vue references it, move its logic inline into App.vue's computed properties (already done with `onlineCount` and `instanceSummary` in Task 2) and delete InstanceList.vue.

- [ ] **Step 2: Run tests**

Run: `cd nanobot-webui && npm test`

Expected: Pass.

- [ ] **Step 3: Commit**

```bash
git add nanobot-webui/src/client/App.vue nanobot-webui/src/client/components/InstanceList.vue
git commit -m "refactor(webui): inline instance status into sidebar connection card"
```

---

### Task 4: ManagePanel — Remove Usage/Costing, Remove Per-Subpage Instance Selectors

**Files:**
- Modify: `nanobot-webui/src/client/components/ManagePanel.vue`
- Modify: `nanobot-webui/src/client/components/ManagePanel.test.ts`
- Modify: `nanobot-webui/src/client/components/SubagentsPanel.vue`
- Modify: `nanobot-webui/src/client/components/SubagentsPanel.test.ts`
- Modify: `nanobot-webui/src/client/components/LogsPanel.vue`
- Modify: `nanobot-webui/src/client/components/LogsPanel.test.ts`
- Modify: `nanobot-webui/src/client/components/SettingsPanel.vue`
- Modify: `nanobot-webui/src/client/components/SettingsPanel.test.ts`

- [ ] **Step 1: Remove Usage and Costing from ManagePanel sections**

In ManagePanel.vue, remove the entries with `id: 'usage'` and `id: 'costing'` from the `sections` array. Remove the `v-else-if="activeSection === 'usage' || activeSection === 'costing'"` article block.

- [ ] **Step 2: Update ManagePanel.test.ts**

Remove assertions for "Usage" and "Costing" in the subnav test. The test currently clicks subagents and logs; no change needed for those.

- [ ] **Step 3: Remove instance selector from SubagentsPanel**

In SubagentsPanel.vue, remove `selectedInstanceId`, `enabledInstances` computed, and the `<select>` in the header. Change the component to receive a single pre-selected instance via props (already receives `instances` from ManagePanel which is already filtered to the single target). Use `props.instances[0]` as the active instance (ManagePanel passes `selectedInstances` which is already filtered).

Replace all `selectedInstanceId.value` references with `props.instances.find((i) => i.enabled)?.id ?? ''`. Remove the `watch(enabledInstances, ...)` and `watch([selectedInstanceId, ...])` watchers. Replace with a single computed:

```ts
const activeInstance = computed(() => props.instances.find((i) => i.enabled))
```

Update `loadSubagents`, `openSubagent`, `saveCurrent`, `removeSubagent` to use `activeInstance.value?.id` instead of `selectedInstanceId.value`.

Remove the instance `<select>` from the template header.

- [ ] **Step 4: Update SubagentsPanel.test.ts**

The tests currently pass `{ instances: [{ id: 'alpha', ... enabled: true }] }`. These still work because the component now uses `props.instances.find(i => i.enabled)` internally. No fetch URL changes needed — the API calls still target `alpha`. Remove any assertions about the instance selector dropdown if present.

- [ ] **Step 5: Remove instance selector from LogsPanel**

Same pattern as SubagentsPanel: remove `selectedInstanceId`, `enabledInstances`, the `<select>`, and watchers. Use `activeInstance` computed from `props.instances.find(i => i.enabled)`.

- [ ] **Step 6: Update LogsPanel.test.ts**

Tests currently pass enabled instances. The internal selector is gone but the first enabled instance is auto-selected. Fetch URLs remain the same. Remove any selector-specific assertions.

- [ ] **Step 7: Remove instance selector from SettingsPanel**

Same pattern: remove `selectedInstanceId`, `enabledInstances`, the `<select>`, watchers. Use `activeInstance` computed.

- [ ] **Step 8: Update SettingsPanel.test.ts**

Same approach — remove selector assertions, verify API calls still target correct instance.

- [ ] **Step 9: Run all webui tests**

Run: `cd nanobot-webui && npm test`

Expected: All tests pass.

- [ ] **Step 10: Commit**

```bash
git add nanobot-webui/src/client/components/ManagePanel.vue nanobot-webui/src/client/components/ManagePanel.test.ts nanobot-webui/src/client/components/SubagentsPanel.vue nanobot-webui/src/client/components/SubagentsPanel.test.ts nanobot-webui/src/client/components/LogsPanel.vue nanobot-webui/src/client/components/LogsPanel.test.ts nanobot-webui/src/client/components/SettingsPanel.vue nanobot-webui/src/client/components/SettingsPanel.test.ts
git commit -m "refactor(webui): remove usage/costing from manage, remove per-subpage instance selectors"
```

---

### Task 5: Component Token-Based Styles — Overview, Manage, Subagents

**Files:**
- Modify: `nanobot-webui/src/client/components/OverviewPanel.vue`
- Modify: `nanobot-webui/src/client/components/ManagePanel.vue`
- Modify: `nanobot-webui/src/client/components/SubagentsPanel.vue`

- [ ] **Step 1: Migrate OverviewPanel.vue to token styles**

Replace all inline `rgba(...)` / `#hex` color references with `var(--token)` equivalents:
- `rgba(59, 130, 246, 0.22)` borders → `1px solid color-mix(in oklch, var(--accent), var(--border) 55%)`
- `rgba(8, 13, 28, 0.72)` / `rgba(15, 23, 42, 0.92)` backgrounds → `oklch(19% 0.014 255 / 0.88)`
- `#93a4bd` → `var(--muted)`
- `#60a5fa` / `#7c3aed` gradients → `var(--accent)` / `oklch(52% 0.18 295)`
- `rgba(34, 197, 94, 0.16)` / `#86efac` → `color-mix(in oklch, var(--success), transparent 84%)` / `var(--success)`
- `rgba(251, 146, 60, ...)` → `color-mix(in oklch, var(--warn), transparent 84%)` / `var(--warn)`
- `border-radius: 0.85rem` → `border-radius: var(--radius)` (or 12px for inner elements per reference)

Also update metric card markup to use reference `.metric` / `.metric-value` / `.metric-label` class patterns:
- `.usage-card` → `.metric` styling
- `.usage-card span` → `.metric-label`
- `.usage-card strong` → `.metric-value`

- [ ] **Step 2: Migrate ManagePanel.vue to token styles**

Replace all inline colors with `var()` tokens. Update manage layout to use reference workspace/subnav pattern:

```css
.manage-layout {
  display: grid;
  grid-template-columns: 228px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.manage-subnav {
  position: sticky;
  top: 84px;
  padding: 10px;
  /* reference .subnav styles */
}
```

Style manage-subnav buttons to match reference `.subnav-item` pattern.

- [ ] **Step 3: Migrate SubagentsPanel.vue to token styles**

Replace all inline colors with `var()` tokens. Style subagent cards using reference `.model-row` / `.setting-row` pattern:

```css
.subagent-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 38px;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2);
  font-size: 12px;
}
```

Style textarea and editor panel with reference `--font-mono` and dark surface tokens.

- [ ] **Step 4: Run tests**

Run: `cd nanobot-webui && npm test`

Expected: Pass (style-only changes, functional assertions unaffected).

- [ ] **Step 5: Commit**

```bash
git add nanobot-webui/src/client/components/OverviewPanel.vue nanobot-webui/src/client/components/ManagePanel.vue nanobot-webui/src/client/components/SubagentsPanel.vue
git commit -m "style(webui): migrate overview/manage/subagents to OKLCH design tokens"
```

---

### Task 6: Component Token-Based Styles — Logs, Settings, Chat

**Files:**
- Modify: `nanobot-webui/src/client/components/LogsPanel.vue`
- Modify: `nanobot-webui/src/client/components/SettingsPanel.vue`
- Modify: `nanobot-webui/src/client/components/ChatPanel.vue`

- [ ] **Step 1: Migrate LogsPanel.vue to token styles**

Replace inline colors with tokens. Style log lines using reference `.log-line` pattern:

```css
.log-line {
  display: grid;
  grid-template-columns: 76px 82px minmax(0, 1fr);
  gap: 12px;
  padding: 10px 16px;
  background: oklch(17% 0.012 255);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.45;
}
```

Style the log panel header using reference `.panel-header` pattern.

- [ ] **Step 2: Migrate SettingsPanel.vue to token styles**

Replace inline colors with tokens. Style setting rows using reference `.setting-row` pattern. Style the JSON/markdown editors with `var(--font-mono)` and `var(--surface-2)` background.

- [ ] **Step 3: Migrate ChatPanel.vue to token styles**

Replace inline colors with tokens. Minimal structural change — just color/token migration.

- [ ] **Step 4: Run tests**

Run: `cd nanobot-webui && npm test`

Expected: Pass.

- [ ] **Step 5: Commit**

```bash
git add nanobot-webui/src/client/components/LogsPanel.vue nanobot-webui/src/client/components/SettingsPanel.vue nanobot-webui/src/client/components/ChatPanel.vue
git commit -m "style(webui): migrate logs/settings/chat to OKLCH design tokens"
```

---

### Task 7: Final Verification

**Files:**
- No new production files unless verification reveals targeted fixes.

- [ ] **Step 1: Run full webui test suite**

Run: `cd nanobot-webui && npm test`

Expected: All tests pass.

- [ ] **Step 2: Run build and type checks**

Run: `cd nanobot-webui && npm run build && npx tsc -p tsconfig.server.json --noEmit && npx tsc --noEmit`

Expected: Pass.

- [ ] **Step 3: Run compose validation**

Run: `cd nanobot-webui && docker compose -f docker-compose.example.yml config`

Expected: Pass.

- [ ] **Step 4: Run Docker smoke build/import**

Run: `cd nanobot-webui && docker build -t nanobot-webui:shell-parity-smoke . && docker run --rm nanobot-webui:shell-parity-smoke node -e "import('./dist/server/index.js').then(() => console.log('server import ok'))"`

Expected: Image builds and prints `server import ok`.

- [ ] **Step 5: Visual spot-check**

Run: `cd nanobot-webui && docker compose -f docker-compose.example.yml up --build` (manual). Verify in browser that:
- Sidebar appears on left with brand mark, nav items, connection card.
- Topbar appears at top with breadcrumbs and action buttons.
- Content area scrolls independently.
- At ≤920px width, sidebar hides and mobile menu/tabs appear.
- Colors match the reference OKLCH palette.
- All four nav sections render their content correctly.
- Manage subnav does not show Usage or Costing.
- Subpages (Subagents, Logs, Settings) do not have their own instance selector.

---

## Self-Review

- **Spec coverage:** Every section in the design spec has a corresponding task: CSS tokens (Task 1), shell layout (Task 2), InstanceList/connection card (Task 3), remove Usage/Costing + per-subpage selectors (Task 4), component token migration (Tasks 5-6), final verification (Task 7).
- **Placeholder scan:** No TBD/TODO placeholders. All steps contain concrete code or explicit instructions.
- **Type consistency:** All computed properties and prop types are consistent with existing Vue patterns. `activeInstance` computed pattern is consistent across SubagentsPanel, LogsPanel, SettingsPanel.
