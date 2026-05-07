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
      <aside data-testid="sidebar-nav" class="sidebar-nav">
        <div class="brand-block">
          <p class="eyebrow">Admin Console</p>
          <h1>Nanobot Web UI</h1>
          <p>Manage live nanobot surfaces from one command deck.</p>
        </div>
        <nav class="dashboard-tabs" aria-label="Dashboard sections">
          <button data-nav="overview" type="button" :class="{ active: activeTab === 'overview' }" @click="activeTab = 'overview'">Overview</button>
          <button data-nav="chat" type="button" :class="{ active: activeTab === 'chat' }" @click="activeTab = 'chat'">Chat Topics</button>
          <button data-nav="instances" type="button" :class="{ active: activeTab === 'instances' }" @click="activeTab = 'instances'">Instances</button>
          <button data-nav="manage" type="button" :class="{ active: activeTab === 'manage' }" @click="activeTab = 'manage'">Manage</button>
        </nav>
      </aside>
      <section class="dashboard-main">
        <header class="top-bar">
          <InstanceList data-testid="instance-status-bar" :instances="instances" />
          <button class="secondary" data-testid="logout-button" type="button" @click="logout">Log out</button>
        </header>
        <section class="content-stage">
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <OverviewPanel v-if="activeTab === 'overview'" :token="token" :instances="instances" />
          <ChatPanel v-else-if="activeTab === 'chat'" :token="token" :instances="instances" />
          <InstancesPanel v-else-if="activeTab === 'instances'" :token="token" :instances="instances" />
          <ManagePanel v-else :token="token" :instances="instances" />
        </section>
      </section>
    </section>
  </main>
</template>

<style>
:root {
  color: #dbe7ff;
  background: #050814;
  font-family:
    Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.18), transparent 34rem),
    radial-gradient(circle at 80% 0%, rgba(14, 165, 233, 0.11), transparent 30rem),
    #050814;
}

button,
input,
select {
  font: inherit;
}

button {
  border: 1px solid rgba(96, 165, 250, 0.45);
  border-radius: 0.65rem;
  background: linear-gradient(135deg, #2563eb, #0891b2);
  color: #fff;
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
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.24);
  transform: translateY(-1px);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.72;
}

input,
select {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 0.65rem;
  background: rgba(15, 23, 42, 0.82);
  color: #e2e8f0;
  min-height: 2.75rem;
  padding: 0 0.85rem;
}

input:focus,
select:focus {
  border-color: #2458d3;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.22);
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

.login-card,
.panel {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 1rem;
  background: rgba(15, 23, 42, 0.78);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.28);
}

.login-card {
  border: 1px solid rgba(148, 163, 184, 0.34);
  border-radius: 1rem;
  background: rgba(15, 23, 42, 0.9);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.34);
}

.login-card {
  display: grid;
  gap: 0.9rem;
  padding: 2rem;
}

.login-card h1,
.brand-block h1 {
  margin: 0;
  color: #f8fbff;
  font-size: clamp(1.7rem, 3vw, 2.25rem);
  letter-spacing: -0.04em;
}

.login-copy,
.brand-block p {
  margin: 0;
  color: #93a4bd;
  line-height: 1.55;
}

.eyebrow {
  margin: 0;
  color: #60a5fa;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

label {
  color: #cbd5e1;
  font-size: 0.9rem;
  font-weight: 700;
}

.dashboard-shell {
  display: grid;
  grid-template-columns: 17rem minmax(0, 1fr);
  min-height: 100vh;
}

.sidebar-nav {
  border-right: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(8, 13, 28, 0.92);
  display: grid;
  gap: 1.5rem;
  grid-template-rows: auto 1fr;
  padding: 1rem;
}

.brand-block {
  display: grid;
  gap: 0.45rem;
  padding: 0.5rem 0.35rem 1rem;
}

.dashboard-main {
  display: grid;
  grid-template-rows: auto 1fr;
  min-width: 0;
}

.top-bar {
  align-items: center;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  min-width: 0;
  padding: 0.85rem 1rem;
}

.content-stage {
  display: grid;
  gap: 1rem;
  min-width: 0;
  padding: 1rem;
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
  color: #94a3b8;
  justify-content: start;
  text-align: left;
}

.dashboard-tabs button.active {
  border-color: rgba(96, 165, 250, 0.32);
  background: rgba(37, 99, 235, 0.18);
  color: #dbeafe;
}

.secondary {
  border: 1px solid rgba(148, 163, 184, 0.28);
  background: rgba(15, 23, 42, 0.72);
  color: #dbe7ff;
}

.secondary:hover:not(:disabled) {
  background: rgba(30, 41, 59, 0.9);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.22);
}

.error {
  border: 1px solid #fecaca;
  border-radius: 0.75rem;
  background: #fff1f2;
  color: #a12135;
  margin: 0;
  padding: 0.8rem 0.95rem;
}

.panel {
  min-width: 0;
  padding: 1.25rem;
}

.panel h2 {
  margin: 0 0 1rem;
  color: #f8fbff;
  font-size: 1rem;
  letter-spacing: -0.01em;
}

@media (max-width: 820px) {
  .dashboard-shell {
    grid-template-columns: 1fr;
  }

  .sidebar-nav {
    border-right: 0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.16);
  }

  .top-bar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
