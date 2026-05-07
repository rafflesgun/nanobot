<script setup lang="ts">
import { ref } from 'vue'
import { fetchInstances, type PublicInstance } from './api'
import InstanceList from './components/InstanceList.vue'
import ChatPanel from './components/ChatPanel.vue'

const token = ref('')
const instances = ref<PublicInstance[]>([])
const error = ref('')
const authenticated = ref(false)
const loading = ref(false)

async function login() {
  error.value = ''
  loading.value = true
  try {
    instances.value = await fetchInstances(token.value)
    authenticated.value = true
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

    <template v-else>
      <header class="dashboard-header">
        <div>
          <p class="eyebrow">Admin Console</p>
          <h1>Nanobot Web UI</h1>
          <p>Monitor configured instances and open websocket chat sessions.</p>
        </div>
        <button class="secondary" data-testid="logout-button" type="button" @click="logout">Log out</button>
      </header>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <div class="grid">
        <InstanceList :instances="instances" />
        <ChatPanel :instances="instances" :token="token" />
      </div>
    </template>
  </main>
</template>

<style>
:root {
  color: #172033;
  background: #f3f6fb;
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
    radial-gradient(circle at top left, rgba(43, 102, 214, 0.12), transparent 32rem),
    linear-gradient(180deg, #f8fbff 0%, #eef3fa 100%);
}

button,
input,
select {
  font: inherit;
}

button {
  border: 0;
  border-radius: 0.65rem;
  background: #2458d3;
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
  background: #1d49b4;
  box-shadow: 0 10px 24px rgba(36, 88, 211, 0.2);
  transform: translateY(-1px);
}

button:disabled {
  cursor: wait;
  opacity: 0.72;
}

input,
select {
  width: 100%;
  border: 1px solid #c9d4e5;
  border-radius: 0.65rem;
  background: #fff;
  color: #172033;
  min-height: 2.75rem;
  padding: 0 0.85rem;
}

input:focus,
select:focus {
  border-color: #2458d3;
  box-shadow: 0 0 0 3px rgba(36, 88, 211, 0.14);
  outline: none;
}

.app-shell {
  width: min(1180px, calc(100vw - 2rem));
  margin: 0 auto;
  padding: 2rem 0;
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
.panel,
.dashboard-header {
  border: 1px solid rgba(148, 163, 184, 0.34);
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 20px 50px rgba(32, 45, 72, 0.1);
}

.login-card {
  display: grid;
  gap: 0.9rem;
  padding: 2rem;
}

.login-card h1,
.dashboard-header h1 {
  margin: 0;
  color: #101827;
  font-size: clamp(1.7rem, 3vw, 2.25rem);
  letter-spacing: -0.04em;
}

.login-copy,
.dashboard-header p {
  margin: 0;
  color: #5b677a;
  line-height: 1.55;
}

.eyebrow {
  margin: 0;
  color: #2458d3;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

label {
  color: #2d394d;
  font-size: 0.9rem;
  font-weight: 700;
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: 1rem;
  padding: 1.35rem 1.5rem;
}

.secondary {
  border: 1px solid #c9d4e5;
  background: #fff;
  color: #24324a;
}

.secondary:hover:not(:disabled) {
  background: #f8fafc;
  box-shadow: 0 8px 20px rgba(32, 45, 72, 0.08);
}

.error {
  border: 1px solid #fecaca;
  border-radius: 0.75rem;
  background: #fff1f2;
  color: #a12135;
  margin: 0;
  padding: 0.8rem 0.95rem;
}

.grid {
  display: grid;
  grid-template-columns: minmax(320px, 0.85fr) minmax(420px, 1.15fr);
  gap: 1rem;
}

.panel {
  min-width: 0;
  padding: 1.25rem;
}

.panel h2 {
  margin: 0 0 1rem;
  color: #101827;
  font-size: 1rem;
  letter-spacing: -0.01em;
}

@media (max-width: 800px) {
  .app-shell {
    width: min(100vw - 1rem, 1180px);
    padding: 0.5rem 0;
  }

  .dashboard-header {
    align-items: stretch;
    flex-direction: column;
  }

  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
