<script setup lang="ts">
import { ref } from 'vue'
import { fetchInstances, type PublicInstance } from './api'
import InstanceList from './components/InstanceList.vue'
import OverviewPanel from './components/OverviewPanel.vue'
import ChatPanel from './components/ChatPanel.vue'
import InstancesPanel from './components/InstancesPanel.vue'
import ManagePanel from './components/ManagePanel.vue'

const token = ref('')
const instances = ref<PublicInstance[]>([])
const error = ref('')
const authenticated = ref(false)
const loading = ref(false)
const activeTab = ref<'overview' | 'chat' | 'instances' | 'manage'>('overview')

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
        <h1>Nanobot Web UI</h1>
        <p class="login-copy">Sign in with your dashboard token to manage configured nanobot instances.</p>
        <label for="dashboard-token">Dashboard token</label>
        <input id="dashboard-token" v-model="token" type="password" placeholder="Dashboard token" autocomplete="current-password" />
        <button type="submit" :disabled="loading">{{ loading ? 'Logging in...' : 'Log in' }}</button>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
      </form>
    </section>

    <section v-else data-testid="dashboard-shell" class="dashboard-shell">
      <header data-testid="floating-header" class="floating-header">
        <div class="floating-actions">
          <InstanceList data-testid="instance-status-bar" :instances="instances" />
          <button class="secondary" data-testid="logout-button" type="button" @click="logout">Log out</button>
        </div>
      </header>

      <div data-testid="main-body" class="main-body">
        <aside data-testid="sidebar-panel" class="sidebar-nav sidebar-panel">
          <div class="brand-block">
            <p class="eyebrow">Admin Console</p>
            <h1>Nanobot Web UI</h1>
            <p>Manage live nanobot surfaces from one command deck.</p>
          </div>
          <nav data-testid="sidebar-nav" class="dashboard-tabs" aria-label="Dashboard sections">
            <button data-nav="overview" type="button" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">Overview</button>
            <button data-nav="chat" type="button" :class="{ active: activeTab === 'chat' }" @click="activeTab = 'chat'">Chat Topics</button>
            <button data-nav="instances" type="button" :class="{ active: activeTab === 'instances' }" @click="activeTab = 'instances'">Instances</button>
            <button data-nav="manage" type="button" :class="{ active: activeTab === 'manage' }" @click="activeTab = 'manage'">Manage</button>
          </nav>
        </aside>

        <section data-testid="content-scroll" class="content-scroll">
          <section data-testid="content-stage" class="content-stage is-top-aligned">
            <p v-if="error" class="error" role="alert">{{ error }}</p>
            <OverviewPanel v-if="activeTab === 'overview'" :token="token" :instances="instances" />
            <ChatPanel v-else-if="activeTab === 'chat'" :token="token" :instances="instances" />
            <InstancesPanel v-else-if="activeTab === 'instances'" :token="token" :instances="instances" />
            <ManagePanel v-else :token="token" :instances="instances" />
          </section>
        </section>
      </div>
    </section>
  </main>
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

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, oklch(35% 0.08 255 / 0.28), transparent 34rem),
    radial-gradient(circle at 80% 0%, oklch(35% 0.08 255 / 0.11), transparent 30rem),
    var(--bg);
}

button,
input,
select {
  font: inherit;
}

button {
  border: 1px solid color-mix(in oklch, var(--accent), var(--border) 58%);
  border-radius: 9px;
  background: linear-gradient(135deg, var(--accent), oklch(54% 0.15 195));
  color: oklch(100% 0 0);
  cursor: pointer;
  font-weight: 700;
  min-height: 2.75rem;
  padding: 0 1rem;
  transition:
    background 150ms ease,
    box-shadow 150ms ease,
    transform 150ms ease;
}

button:hover:not(:disabled) {
  box-shadow: 0 10px 24px oklch(64% 0.18 255 / 0.24);
  transform: translateY(-1px);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.72;
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

.app-shell:not(.is-login) {
  --shell-gutter: 1.5rem;
  --sidebar-width: 17rem;
  height: 100vh;
  overflow: hidden;
}

.app-shell.is-login {
  display: grid;
  min-height: 100vh;
  place-items: center;
}

.login-page {
  width: min(440px, 100%);
}

.login-card,
.panel {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255 / 0.88);
  box-shadow: 0 20px 60px oklch(0% 0 0 / 0.28);
}

.login-card {
  border: 1px solid color-mix(in oklch, var(--border), var(--fg) 10%);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255 / 0.9);
  box-shadow: 0 20px 60px oklch(0% 0 0 / 0.34);
}

.login-card {
  display: grid;
  gap: 0.9rem;
  padding: 2rem;
}

.login-card h1,
.brand-block h1 {
  margin: 0;
  color: var(--fg);
  font-size: clamp(1.7rem, 3vw, 2.25rem);
  letter-spacing: -0.04em;
}

.login-copy,
.brand-block p {
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

.dashboard-shell {
  min-height: 100vh;
  position: relative;
}

.floating-header {
  pointer-events: none;
  position: fixed;
  inset: 0 0 auto;
  z-index: 20;
}

.floating-actions {
  align-items: center;
  backdrop-filter: blur(16px);
  background: oklch(16% 0.012 255 / 0.9);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  margin: var(--shell-gutter) var(--shell-gutter) 0 auto;
  max-width: calc(100vw - var(--sidebar-width) - var(--shell-gutter) * 4);
  padding: 0.45rem;
  pointer-events: auto;
  width: max-content;
}

.main-body {
  display: flex;
  gap: 2rem;
  height: 100vh;
  overflow: hidden;
  padding: var(--shell-gutter);
}

.sidebar-nav {
  backdrop-filter: blur(18px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(16% 0.012 255 / 0.9);
  display: grid;
  gap: 1.5rem;
  grid-template-rows: auto 1fr;
  flex: 0 0 var(--sidebar-width);
  height: calc(100vh - var(--shell-gutter) * 2);
  overflow-y: auto;
  padding: 1.1rem;
}

.brand-block {
  display: grid;
  gap: 0.45rem;
  padding: 0.5rem 0.35rem 1rem;
}

.content-scroll {
  flex: 1;
  height: calc(100vh - var(--shell-gutter) * 2);
  min-width: 0;
  overflow-y: auto;
}

.content-stage {
  align-content: start;
  display: grid;
  gap: 1rem;
  min-width: 0;
  padding: 5rem clamp(1rem, 3vw, 2.5rem) 2.5rem;
}

.dashboard-tabs {
  align-content: start;
  display: grid;
  gap: 0.55rem;
  margin: 0;
}

.dashboard-tabs button {
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  justify-content: start;
  text-align: left;
}

.dashboard-tabs button.active {
  border-color: color-mix(in oklch, var(--accent), var(--border) 58%);
  background: oklch(64% 0.18 255 / 0.18);
  color: var(--fg);
}

.secondary {
  border: 1px solid var(--border);
  background: oklch(14% 0.012 255 / 0.72);
  color: var(--fg);
}

.secondary:hover:not(:disabled) {
  background: var(--surface-2);
  box-shadow: 0 8px 20px oklch(0% 0 0 / 0.22);
}

.error {
  border: 1px solid var(--danger);
  border-radius: 12px;
  background: oklch(68% 0.17 25 / 0.15);
  color: oklch(50% 0.17 25);
  margin: 0;
  padding: 0.8rem 0.95rem;
}

.panel {
  min-width: 0;
  padding: 1.25rem;
}

.panel h2 {
  margin: 0 0 1rem;
  color: var(--fg);
  font-size: 1rem;
  letter-spacing: -0.01em;
}

@media (max-width: 820px) {
  .app-shell:not(.is-login) {
    height: auto;
    overflow: visible;
  }

  .main-body {
    display: grid;
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }

  .sidebar-nav,
  .content-scroll {
    height: auto;
  }

  .floating-actions {
    margin-left: var(--shell-gutter);
    max-width: calc(100vw - var(--shell-gutter) * 2);
    width: auto;
  }

  .content-stage {
    padding: 1rem 0 2rem;
  }
}
</style>
