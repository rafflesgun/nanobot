<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { fetchInstances, type PublicInstance } from './api'
import OverviewPanel from './components/OverviewPanel.vue'
import ChatView from './components/chat/ChatView.vue'
import InstancesPanel from './components/InstancesPanel.vue'
import LogsPanel from './components/LogsPanel.vue'
import ManagePanel from './components/ManagePanel.vue'

const token = ref('')
const instances = ref<PublicInstance[]>([])
const error = ref('')
const authenticated = ref(false)
const loading = ref(false)
const activeTab = ref<'overview' | 'chat' | 'instances' | 'manage' | 'logs'>('overview')
const sidebarCollapsed = ref(false)
const mobileMenuOpen = ref(false)

const activeTabLabel = computed(() => {
  const map: Record<string, string> = { overview: 'Overview', chat: 'Chat', instances: 'Instances', manage: 'Manage', logs: 'Logs' }
  return map[activeTab.value] ?? 'Overview'
})

const onlineCount = computed(() => instances.value.filter(i => i.enabled).length)

const enabledInstances = computed(() => instances.value.filter(i => i.enabled))

const breadcrumbInstance = computed(() => {
  if (activeTab.value !== 'manage') return null
  return enabledInstances.value[0] ?? null
})

const manageSectionCount = computed(() => 6)

const logsInstanceId = ref('')

watch(enabledInstances, (ei) => {
  if (!ei.some((i) => i.id === logsInstanceId.value)) logsInstanceId.value = ei[0]?.id ?? ''
}, { immediate: true })

async function login() {
  error.value = ''
  loading.value = true
  try {
    instances.value = await fetchInstances(token.value)
    authenticated.value = true
    activeTab.value = 'overview'
  } catch (err) {
    authenticated.value = false
    instances.value = []
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

function logout() {
  token.value = ''
  instances.value = []
  error.value = ''
  authenticated.value = false
  activeTab.value = 'overview'
}
</script>

<template>
  <main class="app-shell" :class="{ 'is-login': !authenticated }">
    <section v-if="!authenticated" class="login-page" aria-label="Dashboard login">
      <form class="login-card" @submit.prevent="login">
        <p class="eyebrow">Admin Console</p>
        <h1>Nanobot Dashboard</h1>
        <p class="login-copy">Sign in with your dashboard token to manage configured nanobot instances.</p>
        <label for="dashboard-token">Dashboard token</label>
        <input id="dashboard-token" v-model="token" type="password" placeholder="Dashboard token" autocomplete="current-password" />
        <button type="submit" :disabled="loading">{{ loading ? 'Logging in...' : 'Log in' }}</button>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </form>
    </section>

    <div v-else data-testid="dashboard-shell" class="app" :class="{ 'is-collapsed': sidebarCollapsed }">
      <aside class="sidebar" :class="{ 'is-collapsed': sidebarCollapsed }" aria-label="Primary navigation">
        <div class="brand">
          <div class="brand-mark">
            <div class="logo">nb</div>
            <div class="brand-text">
              <h1>nanobot</h1>
              <p>local agent console</p>
            </div>
          </div>
          <button class="icon-button" aria-label="Collapse sidebar" @click="sidebarCollapsed = !sidebarCollapsed">⌘</button>
        </div>

        <nav class="nav-section" aria-label="Main">
          <div class="section-label">Workspace</div>
          <button data-nav="overview" class="nav-item" :class="{ 'is-active': activeTab === 'overview' }" @click="activeTab = 'overview'"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Overview</span></span><span class="count">{{ instances.length.toString().padStart(2, '0') }}</span></button>
          <button data-nav="chat" class="nav-item" :class="{ 'is-active': activeTab === 'chat' }" @click="activeTab = 'chat'"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Chat</span></span><span class="count">0</span></button>
          <button data-nav="instances" class="nav-item" :class="{ 'is-active': activeTab === 'instances' }" @click="activeTab = 'instances'"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Instances</span></span><span class="count">{{ instances.length.toString().padStart(2, '0') }}</span></button>
          <button data-nav="manage" class="nav-item" :class="{ 'is-active': activeTab === 'manage' }" @click="activeTab = 'manage'"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Manage</span></span><span class="count">{{ manageSectionCount }}</span></button>
          <button data-nav="logs" class="nav-item" :class="{ 'is-active': activeTab === 'logs' }" @click="activeTab = 'logs'"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Logs</span></span><span class="count">live</span></button>
        </nav>

        <div class="sidebar-bottom">
          <div class="connection-card">
            <div class="connection-row">
              <div class="connection-title">Gateway</div>
              <span class="pill"><span class="dot" :class="{ success: onlineCount > 0 }"></span>{{ onlineCount > 0 ? 'online' : 'offline' }}</span>
            </div>
            <div v-if="instances.length === 0" class="muted mono" style="font-size: 11px; line-height: 1.5;">No instances</div>
            <div v-else class="connection-instances">
              <span v-for="instance in instances" :key="instance.id" class="connection-pill" :title="`${instance.name} (${instance.enabled ? 'enabled' : 'disabled'})`">
                <span class="dot" :class="instance.enabled ? 'success' : 'danger'"></span>
                <span>{{ instance.name }}</span>
              </span>
            </div>
          </div>
        </div>
      </aside>

      <main class="main">
        <header class="topbar">
          <button class="icon-button mobile-menu" aria-label="Open navigation" @click="mobileMenuOpen = !mobileMenuOpen">☰</button>
          <div class="crumbs"><span>nanobot</span><span>/</span><strong>{{ activeTabLabel }}</strong><template v-if="breadcrumbInstance"><span>/</span><span>{{ breadcrumbInstance.name }}</span></template></div>
          <div class="top-actions">
            <span class="pill"><span class="dot success"></span>{{ onlineCount }} online</span>
            <button class="button" data-testid="refresh-button" @click="login()">↻ Refresh</button>
            <button class="button primary" data-testid="new-chat-button" @click="activeTab = 'chat'">+ New chat</button>
            <button class="button" data-testid="logout-button" @click="logout">Log out</button>
          </div>
        </header>

        <div class="mobile-tabs" aria-label="Mobile navigation">
          <button class="pill" :class="{ 'is-active': activeTab === 'overview' }" @click="activeTab = 'overview'">Overview</button>
          <button class="pill" :class="{ 'is-active': activeTab === 'chat' }" @click="activeTab = 'chat'">Chat</button>
          <button class="pill" :class="{ 'is-active': activeTab === 'instances' }" @click="activeTab = 'instances'">Instances</button>
          <button class="pill" :class="{ 'is-active': activeTab === 'manage' }" @click="activeTab = 'manage'">Manage</button>
          <button class="pill" :class="{ 'is-active': activeTab === 'logs' }" @click="activeTab = 'logs'">Logs</button>
        </div>

        <section class="content" :class="{ 'chat-content': activeTab === 'chat' }">
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <OverviewPanel v-if="activeTab === 'overview'" :token="token" :instances="instances" />
          <ChatView v-else-if="activeTab === 'chat'" :token="token" :instances="instances" />
          <InstancesPanel v-else-if="activeTab === 'instances'" :token="token" :instances="instances" />
          <ManagePanel v-else-if="activeTab === 'manage'" :token="token" :instances="instances" />
          <section v-else-if="activeTab === 'logs'" class="logs-page">
            <div class="panel-heading">
              <div><h2>Logs</h2><p>Instance log viewer</p></div>
              <label v-if="enabledInstances.length > 0" class="target-select"><span>Target instance</span><select v-model="logsInstanceId"><option v-for="inst in enabledInstances" :key="inst.id" :value="inst.id">{{ inst.name }}</option></select></label>
            </div>
            <LogsPanel :token="token" :instance="enabledInstances.find((i) => i.id === logsInstanceId)" />
          </section>
        </section>
      </main>
    </div>
  </main>

  <Teleport to="body">
    <div v-if="mobileMenuOpen" class="drawer-backdrop" @click="mobileMenuOpen = false"></div>
    <aside v-if="mobileMenuOpen" class="mobile-drawer" aria-label="Mobile navigation">
      <nav class="nav-section">
        <div class="section-label">Workspace</div>
        <button data-nav="overview" class="nav-item" :class="{ 'is-active': activeTab === 'overview' }" @click="activeTab = 'overview'; mobileMenuOpen = false"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Overview</span></span></button>
        <button data-nav="chat" class="nav-item" :class="{ 'is-active': activeTab === 'chat' }" @click="activeTab = 'chat'; mobileMenuOpen = false"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Chat</span></span></button>
        <button data-nav="instances" class="nav-item" :class="{ 'is-active': activeTab === 'instances' }" @click="activeTab = 'instances'; mobileMenuOpen = false"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Instances</span></span></button>
        <button data-nav="manage" class="nav-item" :class="{ 'is-active': activeTab === 'manage' }" @click="activeTab = 'manage'; mobileMenuOpen = false"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Manage</span></span></button>
        <button data-nav="logs" class="nav-item" :class="{ 'is-active': activeTab === 'logs' }" @click="activeTab = 'logs'; mobileMenuOpen = false"><span class="nav-left"><span class="nav-icon"></span><span class="nav-label">Logs</span></span></button>
      </nav>
    </aside>
  </Teleport>
</template>

<style>
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

* {
  box-sizing: border-box;
}

*::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

*::-webkit-scrollbar-track {
  background: transparent;
}

*::-webkit-scrollbar-thumb {
  background: oklch(30% 0.012 255);
  border-radius: 3px;
}

*::-webkit-scrollbar-thumb:hover {
  background: oklch(40% 0.014 255);
}

* {
  scrollbar-width: thin;
  scrollbar-color: oklch(30% 0.012 255) transparent;
}

html {
  min-height: 100%;
  background: var(--bg);
}

body {
  margin: 0;
  min-height: 100vh;
  font-family: var(--font-body);
  color: var(--fg);
  background:
    radial-gradient(circle at 72% -20%, oklch(35% 0.08 255 / 0.28), transparent 34rem),
    linear-gradient(180deg, oklch(18% 0.014 255), var(--bg) 26rem);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

button,
input,
select {
  font: inherit;
}

button {
  cursor: pointer;
}

input,
select {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: oklch(19% 0.014 255 / 0.88);
  color: var(--fg);
  min-height: 2.75rem;
  padding: 0 0.85rem;
}

input:focus,
select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px oklch(64% 0.18 255 / 0.22);
  outline: none;
}

.app-shell {
  min-height: 100vh;
}

.app-shell.is-login {
  display: grid;
  min-height: 100vh;
  place-items: center;
}

.login-page {
  width: min(440px, 100%);
}

.login-card {
  border: 1px solid color-mix(in oklch, var(--border), var(--fg) 10%);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255 / 0.9);
  box-shadow: 0 20px 60px oklch(0% 0 0 / 0.34);
  display: grid;
  gap: 0.9rem;
  padding: 2rem;
}

.login-card h1 {
  margin: 0;
  color: var(--fg);
  font-size: clamp(1.7rem, 3vw, 2.25rem);
  letter-spacing: -0.04em;
}

.login-copy {
  margin: 0;
  color: var(--muted);
  line-height: 1.55;
}

.eyebrow {
  margin: 0;
  color: var(--accent);
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

label {
  color: var(--fg);
  font-size: 0.9rem;
  font-weight: 700;
}

.login-card button {
  border: 1px solid color-mix(in oklch, var(--accent), var(--border) 58%);
  border-radius: 9px;
  background: linear-gradient(135deg, var(--accent), oklch(54% 0.15 195));
  color: oklch(100% 0 0);
  cursor: pointer;
  font-weight: 700;
  min-height: 2.75rem;
  padding: 0 1rem;
  transition: background 150ms ease, box-shadow 150ms ease, transform 150ms ease;
}

.login-card button:hover:not(:disabled) {
  box-shadow: 0 10px 24px oklch(64% 0.18 255 / 0.24);
  transform: translateY(-1px);
}

.login-card button:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

.app {
  display: grid;
  grid-template-columns: 268px minmax(0, 1fr);
  min-height: 100vh;
}

.app.is-collapsed {
  grid-template-columns: 64px minmax(0, 1fr);
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

.sidebar.is-collapsed {
  overflow: hidden;
}

.sidebar.is-collapsed .brand-text,
.sidebar.is-collapsed .section-label,
.sidebar.is-collapsed .nav-label,
.sidebar.is-collapsed .count,
.sidebar.is-collapsed .connection-card,
.sidebar.is-collapsed .sidebar-bottom .connection-instances {
  display: none;
}

.sidebar.is-collapsed .nav-item {
  justify-content: center;
  padding: 8px;
  overflow: hidden;
}

.sidebar.is-collapsed .brand {
  justify-content: center;
  padding: 18px 8px 14px;
}

.sidebar.is-collapsed .sidebar-bottom {
  padding: 12px 8px;
}

.brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 16px 14px;
}

.brand-mark {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.logo {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border: 1px solid color-mix(in oklch, var(--accent), var(--border) 58%);
  border-radius: 9px;
  background: oklch(21% 0.05 255);
  color: var(--fg);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.brand h1 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 15px;
  line-height: 1.1;
  letter-spacing: -0.02em;
}

.brand p {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.2;
}

.icon-button {
  display: inline-grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--surface);
  color: var(--muted);
}

.nav-section {
  padding: 10px;
}

.section-label {
  margin: 10px 8px 7px;
  color: var(--muted);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.nav-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  min-height: 34px;
  padding: 8px 9px;
  border: 1px solid transparent;
  border-radius: 9px;
  background: transparent;
  color: var(--muted);
  text-align: start;
  font-size: 13px;
  line-height: 1.2;
}

.nav-item + .nav-item {
  margin-block-start: 2px;
}

.nav-item.is-active {
  border-color: var(--border);
  background: var(--surface);
  color: var(--fg);
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.nav-icon {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--border);
}

.is-active .nav-icon {
  background: var(--accent);
}

.count {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.sidebar-bottom {
  margin-block-start: auto;
  padding: 12px 10px;
  border-block-start: 1px solid var(--border);
}

.connection-card {
  padding: 11px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
}

.connection-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-block-end: 8px;
}

.connection-title {
  font-size: 12px;
  font-weight: 600;
}

.connection-instances {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.connection-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--fg);
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
  padding: 4px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--fg);
  font-size: 11px;
  font-weight: 560;
  white-space: nowrap;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--muted);
}

.dot.success {
  background: var(--success);
}

.dot.danger {
  background: var(--danger);
}

.muted {
  color: var(--muted);
}

.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}

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

.mobile-menu {
  display: none;
}

.crumbs {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  color: var(--muted);
  font-size: 12px;
}

.crumbs strong {
  color: var(--fg);
  font-weight: 600;
}

.top-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
}

.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 34px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 9px;
  background: var(--surface);
  color: var(--fg);
  font-size: 12px;
  font-weight: 560;
  white-space: nowrap;
}

.button.primary {
  border-color: color-mix(in oklch, var(--accent), black 10%);
  background: var(--accent);
  color: oklch(99% 0.002 255);
}

.content {
  width: min(100%, 1440px);
  margin-inline: auto;
  padding: 22px;
}

.content.chat-content {
  width: 100%;
  max-width: none;
  padding: 0;
}

.logs-page {
  display: grid;
  gap: 1rem;
}

.panel-heading {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.panel-heading p {
  color: var(--muted);
  margin: 0.25rem 0 0;
}

.target-select {
  display: grid;
  gap: 0.45rem;
  min-width: 16rem;
}

.target-select span {
  color: var(--fg);
  font-weight: 700;
}

.mobile-tabs {
  display: none;
  gap: 6px;
  overflow-x: auto;
  padding: 10px 14px;
  border-block-end: 1px solid var(--border);
  background: var(--surface);
}

.mobile-tabs .pill {
  flex: 0 0 auto;
}

.error {
  border: 1px solid var(--danger);
  border-radius: 12px;
  background: oklch(68% 0.17 25 / 0.15);
  color: oklch(50% 0.17 25);
  margin: 0;
  padding: 0.8rem 0.95rem;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.001ms !important;
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
  }
}

@media (max-width: 1180px) {
  .content {
    padding: 18px;
  }
  .hero {
    grid-template-columns: 1fr;
  }
  .workspace {
    grid-template-columns: 196px minmax(0, 1fr);
  }
  .span-4,
  .span-5,
  .span-7 {
    grid-column: span 6;
  }
}

@media (max-width: 920px) {
  .app {
    grid-template-columns: 1fr;
  }

  .sidebar {
    display: none;
  }

  .mobile-menu {
    display: inline-grid;
  }

  .mobile-tabs {
    display: flex;
  }

  .topbar {
    grid-template-columns: auto minmax(0, 1fr);
    padding: 10px 14px;
  }

  .content {
    padding: 14px;
  }
  .top-actions .button:not(.primary),
  .top-actions .pill {
    display: none;
  }
  .workspace {
    grid-template-columns: 1fr;
  }
  .hero-panel {
    padding: 18px;
  }
  .hero-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .span-4,
  .span-5,
  .span-7,
  .span-12 {
    grid-column: span 12;
  }
}

.drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  background: oklch(0% 0 0 / 0.5);
}

.mobile-drawer {
  position: fixed;
  inset-block: 0;
  inset-inline-start: 0;
  z-index: 50;
  width: 268px;
  border-inline-end: 1px solid var(--border);
  background: oklch(16% 0.012 255 / 0.97);
  backdrop-filter: blur(18px);
  padding: 18px 10px;
  overflow-y: auto;
}

@media (max-width: 620px) {
  .crumbs {
    font-size: 11px;
  }
  .topbar {
    min-height: 56px;
  }
  .content {
    padding: 10px;
  }
  .hero-panel,
  .card {
    border-radius: 12px;
    padding: 14px;
  }
  .hero-head {
    flex-direction: column;
    margin-block-end: 16px;
  }
  .hero h2 {
    font-size: 30px;
  }
  .hero-metrics {
    grid-template-columns: 1fr;
  }
  .runtime-meta {
    grid-template-columns: 1fr;
  }
  .workgrid {
    gap: 10px;
  }
  .panel-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
