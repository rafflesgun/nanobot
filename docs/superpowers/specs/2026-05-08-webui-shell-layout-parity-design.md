# WebUI Shell Layout Parity Design

**Goal:** Make the nanobot-webui visual shell, layout, colors, sidebar, topbar, and CSS match the dark layout reference `.superpowers/nanobot-dashboard-dark-layout.html` with strict parity, while preserving existing Nanobot dashboard content, data bindings, menu items, and subpage functionality.

**Approach:** Shell/CSS parity with existing components (Approach 1 from brainstorming). Rebuild the global app shell and visual tokens to match the reference structure and design language. Update component panel/card/button/table/log styling to use the same visual system. Keep page component markup and data bindings mostly intact, adjusting only where needed for shell alignment or to remove redundant per-subpage instance selectors.

**Reference:** `.superpowers/nanobot-dashboard-dark-layout.html` — the exact visual target for CSS tokens, layout grid, sidebar, topbar, spacing, radii, typography, responsive breakpoints, and color scheme.

---

## Changes Summary

### App Shell (`App.vue`)
- Replace the current floating-header + padded-flex-body shell with the reference structure:
  - Two-column app grid: `grid-template-columns: 268px minmax(0, 1fr)` at full width.
  - Sticky sidebar occupying the left column, full viewport height.
  - Main area with sticky topbar + scrollable content below.
- Sidebar matches the reference visually:
  - Brand mark: logo icon + "nanobot" title + "local agent console" subtitle.
  - Collapse sidebar button (icon-button style from reference).
  - Section labels ("Workspace" heading above nav buttons).
  - Nav items with dot icons, active state matching reference (`border-color: var(--border); background: var(--surface); color: var(--fg)`).
  - Sidebar bottom: connection-card showing gateway status (online/idle/disconnected from real instance status data).
  - Glass/frosted background: `backdrop-filter: blur(18px)` + translucent dark background.
- Topbar matches the reference visually:
  - Sticky, `z-index: 5`, `backdrop-filter: blur(18px)` + translucent dark background.
  - Breadcrumbs: "nanobot / [Active Section] / [Instance name if applicable]".
  - Top-actions area: real Nanobot actions (Refresh, New Chat) styled as reference `.button` / `.button.primary`.
  - Instance status pills in top-actions or sidebar bottom (not inline in a floating island).
- Content area: `width: min(100%, 1440px); margin-inline: auto; padding: 22px;` matching reference `.content`.
- Responsive breakpoints match reference:
  - ≤1180px: sidebar narrows, hero columns collapse.
  - ≤920px: sidebar hidden, mobile-menu button appears in topbar, mobile-tabs row appears below topbar.
  - ≤620px: tighter padding, hero metrics go single-column, panel headers stack.

### Color System
- Replace all inline rgba/hex colors with CSS custom properties matching the reference OKLCH palette:
  - `--bg: oklch(15% 0.012 255)` (deep dark background)
  - `--surface: oklch(19% 0.014 255)` (panel/card background)
  - `--surface-2: oklch(23% 0.014 255)` (metric/row inner surfaces)
  - `--fg: oklch(94% 0.006 255)` (primary text)
  - `--muted: oklch(66% 0.012 255)` (secondary/muted text)
  - `--border: oklch(29% 0.012 255)` (all borders)
  - `--accent: oklch(64% 0.18 255)` (blue accent for active/primary)
  - `--success: oklch(70% 0.14 145)` (green status)
  - `--warn: oklch(78% 0.14 85)` (orange warning)
  - `--danger: oklch(68% 0.17 25)` (red error)
  - `--radius: 14px` (card/panel border radius)
  - `--font-display`, `--font-body`, `--font-mono` matching reference typography stack.
- All component scoped styles migrate from inline rgba/hex to these tokens.

### Sidebar Navigation Items
- Keep existing Nanobot menu items: Overview, Chat Topics, Instances, Manage.
- Top-level Logs nav item is NOT added (Logs remains under Manage subnav only).
- Pinned chats section is NOT added (not in current feature scope).
- Nav items rendered with reference styling: dot icon, active state, optional count badges.

### Manage Panel (`ManagePanel.vue`)
- Remove Usage and Costing from the subnav sections list (they live on Overview).
- Keep: Settings, Subagents, Logs, Session, Memory, Restart.
- Remove per-subpage instance selectors from SubagentsPanel, LogsPanel, SettingsPanel.
  - Each subpage receives `selectedInstances` from the parent ManagePanel's target-instance selector.
  - SubagentsPanel, LogsPanel, SettingsPanel props change from `{ instances: PublicInstance[] }` to `{ instances: PublicInstance[] }` where the parent already filters to the single selected target.
  - This means the subpage component receives the already-filtered single-instance array and no longer needs its own `<select>` or filtering logic.
- Manage layout uses reference workspace/subnav pattern:
  - `.workspace` grid: `grid-template-columns: 228px minmax(0, 1fr)`.
  - Left: `.subnav` sticky panel with instance name + section buttons.
  - Right: content area.

### Overview Panel (`OverviewPanel.vue`)
- Keep existing usage cards/trend/breakdown/status cards.
- Apply reference visual system: metric cards use `--surface-2` background, metric-value font, metric-label font.
- Status cards use reference card/row styling.
- Usage panel uses reference hero-panel card styling with `--border`, `--surface`, `--radius`.

### Subagents Panel (`SubagentsPanel.vue`)
- Remove the instance selector dropdown.
- Accept the parent-filtered `instances` prop (single selected target instance).
- Apply reference card/row styling: subagent-card rows use `.model-row` / `.setting-row` visual pattern.
- Markdown editor textarea uses reference `--font-mono` and dark surface styling.

### Logs Panel, Settings Panel, Chat Panel
- Remove per-panel instance selectors (same as SubagentsPanel).
- Apply reference card/table/log visual styling.

### Component Visual Language
- All `.panel` / `.card` elements use `border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88)`.
- All `.button` elements use reference button styling.
- `.button.primary` uses accent background with dark text.
- `.secondary` buttons use `--surface` background with `--fg` text.
- Status pills use reference `.pill` styling with dot indicators.
- Tables use reference table styling (dense, monospace, uppercase headers).
- Log lines use reference `.log-line` styling.

### Login Page
- Keep existing login card functionality.
- Apply reference card styling: `--border`, `--surface`, `--radius`, `--fg`, `--muted`, `--accent` for the eyebrow and submit button.

---

## Files Changed

- `nanobot-webui/src/client/App.vue`: rebuild shell layout, add CSS tokens, topbar, sidebar, responsive breakpoints.
- `nanobot-webui/src/client/components/OverviewPanel.vue`: migrate to token-based styles, reference metric/card styling.
- `nanobot-webui/src/client/components/ManagePanel.vue`: remove Usage/Costing from sections, remove per-subpage instance selectors, apply reference workspace/subnav layout.
- `nanobot-webui/src/client/components/SubagentsPanel.vue`: remove instance selector, accept parent-filtered instances, apply reference card styling.
- `nanobot-webui/src/client/components/LogsPanel.vue`: remove instance selector, apply reference log/table styling.
- `nanobot-webui/src/client/components/SettingsPanel.vue`: remove instance selector, apply reference card/row styling.
- `nanobot-webui/src/client/components/ChatPanel.vue`: apply reference visual tokens (minimal structural change).
- `nanobot-webui/src/client/components/InstanceList.vue`: restyle as sidebar bottom connection-card.
- Corresponding test files: update expectations for removed instance selectors, changed Manage sections, token-based style assertions.

## Out of Scope

- Adding top-level Logs nav item.
- Adding pinned chats sidebar section.
- Adding runtime topology visualization.
- Rebuilding Overview into the reference hero/runtime/workgrid composition (content stays as usage + status cards, but visual styling matches reference).
- Adding breadcrumbs beyond "nanobot / [section] / [instance]".
- Changing backend API behavior.