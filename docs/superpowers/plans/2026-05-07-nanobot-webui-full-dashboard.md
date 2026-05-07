# Nanobot WebUI Full Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the login-gated `nanobot-webui` MVP into a usable full dashboard with overview/status, multi-instance group chat, logs, and settings.

**Architecture:** Keep the browser security model: the browser only knows the dashboard token and public instance metadata; nanobot admin tokens and websocket tokens stay server-side. Reuse the existing webui BFF proxy for `/admin/v1/status`, `/admin/v1/logs`, and `/admin/v1/settings`; extend the Socket.IO chat bridge to manage one upstream websocket per selected instance.

**Tech Stack:** Vue 3 `<script setup>`, Vitest, Vue Test Utils, Koa, Socket.IO, `ws`, TypeScript, Docker.

---

## File Structure

- Modify `nanobot-webui/src/client/api.ts`: add typed helpers for instance admin status, logs, log tails, and settings.
- Modify `nanobot-webui/src/client/socket.ts`: expose typed group chat socket helpers.
- Modify `nanobot-webui/src/server/chatBridge.ts`: replace single active upstream state with a per-socket `Map<instanceId, upstream>` and add group connect/disconnect semantics.
- Modify `nanobot-webui/src/server/chatBridge.test.ts`: add red/green tests for multiple upstream connections and broadcast sends.
- Create `nanobot-webui/src/client/components/OverviewPanel.vue`: load and render per-instance status cards.
- Create `nanobot-webui/src/client/components/OverviewPanel.test.ts`: component tests for successful status and degraded status.
- Replace `nanobot-webui/src/client/components/ChatPanel.vue`: turn placeholder into group chat UI.
- Create `nanobot-webui/src/client/components/ChatPanel.test.ts`: tests for selection, send behavior, and labeled transcript.
- Create `nanobot-webui/src/client/components/LogsPanel.vue`: read-only log list and tail viewer.
- Create `nanobot-webui/src/client/components/LogsPanel.test.ts`: tests for log selection, tail rendering, and errors.
- Create `nanobot-webui/src/client/components/SettingsPanel.vue`: small model/provider settings editor.
- Create `nanobot-webui/src/client/components/SettingsPanel.test.ts`: tests for loading, patching, and restart warning.
- Modify `nanobot-webui/src/client/App.vue`: add tabs for Overview, Group Chat, Logs, Settings; pass the in-memory dashboard token to panels.
- Modify `nanobot-webui/src/client/App.test.ts`: verify login gating plus tab navigation.
- Modify `nanobot-webui/src/server/index.test.ts`: add proxy regression tests for status/logs/settings paths if current coverage is insufficient.

## Task 1: API Client Helpers

**Files:**
- Modify: `nanobot-webui/src/client/api.ts`
- Create: `nanobot-webui/src/client/api.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `nanobot-webui/src/client/api.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchInstanceLogs, fetchInstanceSettings, fetchInstanceStatus, fetchLogTail, patchInstanceSettings } from './api'

describe('admin API helpers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads instance status through the dashboard proxy', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ status: 'ok', model: 'gpt-4.1', provider: 'openai', uptime_s: 12.5, channels: ['websocket'], websocket: { enabled: true } })
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchInstanceStatus('alpha', 'dashboard')).resolves.toMatchObject({ status: 'ok', model: 'gpt-4.1' })

    expect(fetchMock).toHaveBeenCalledWith('/api/instances/alpha/status', { headers: { authorization: 'Bearer dashboard' } })
  })

  it('loads log names and tails through the dashboard proxy', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ logs: [{ name: 'nanobot.log' }] }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ name: 'nanobot.log', lines: ['one', 'two'] }) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchInstanceLogs('alpha', 'dashboard')).resolves.toEqual([{ name: 'nanobot.log' }])
    await expect(fetchLogTail('alpha', 'nanobot.log', 'dashboard')).resolves.toEqual({ name: 'nanobot.log', lines: ['one', 'two'] })

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/instances/alpha/logs', { headers: { authorization: 'Bearer dashboard' } })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/instances/alpha/logs/nanobot.log?tail=200', { headers: { authorization: 'Bearer dashboard' } })
  })

  it('loads and patches settings through the dashboard proxy', async () => {
    const settings = { agent: { model: 'gpt-4.1', provider: 'auto', resolved_provider: 'openai', has_api_key: true }, requires_restart: false }
    const updated = { agent: { model: 'gpt-4.1-mini', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: true }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue(settings) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue(updated) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchInstanceSettings('alpha', 'dashboard')).resolves.toEqual(settings)
    await expect(patchInstanceSettings('alpha', 'dashboard', { model: 'gpt-4.1-mini', provider: 'openai' })).resolves.toEqual(updated)

    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/instances/alpha/settings', {
      method: 'PATCH',
      headers: { authorization: 'Bearer dashboard', 'content-type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4.1-mini', provider: 'openai' })
    })
  })

  it('throws clear errors for failed admin proxy calls', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: vi.fn() }))

    await expect(fetchInstanceStatus('alpha', 'dashboard')).rejects.toThrow('failed to load status for alpha: 503')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd nanobot-webui && npm test -- src/client/api.test.ts`

Expected: FAIL with missing exports such as `fetchInstanceStatus`.

- [ ] **Step 3: Implement the API helpers**

Replace `nanobot-webui/src/client/api.ts` with:

```ts
export type PublicInstance = {
  id: string
  name: string
  baseUrl: string
  enabled: boolean
}

export type InstanceStatus = {
  status: string
  model?: string
  provider?: string
  resolved_provider?: string
  uptime_s?: number
  channels?: string[]
  websocket?: { enabled?: boolean }
}

export type LogInfo = { name: string }
export type LogTail = { name: string; lines: string[] }

export type InstanceSettings = {
  agent: {
    model: string
    provider: string
    resolved_provider: string
    has_api_key: boolean
  }
  requires_restart: boolean
}

export type SettingsPatch = {
  model?: string
  provider?: string
}

function authHeaders(token: string) {
  return { authorization: `Bearer ${token}` }
}

async function readJson<T>(res: Response, errorMessage: string): Promise<T> {
  if (!res.ok) throw new Error(`${errorMessage}: ${res.status}`)
  return (await res.json()) as T
}

export async function fetchInstances(token: string): Promise<PublicInstance[]> {
  const res = await fetch('/api/instances', { headers: authHeaders(token) })
  const payload = await readJson<{ instances: PublicInstance[] }>(res, 'failed to load instances')
  return payload.instances
}

export async function fetchInstanceStatus(instanceId: string, token: string): Promise<InstanceStatus> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/status`, { headers: authHeaders(token) })
  return readJson<InstanceStatus>(res, `failed to load status for ${instanceId}`)
}

export async function fetchInstanceLogs(instanceId: string, token: string): Promise<LogInfo[]> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/logs`, { headers: authHeaders(token) })
  const payload = await readJson<{ logs: LogInfo[] }>(res, `failed to load logs for ${instanceId}`)
  return payload.logs
}

export async function fetchLogTail(instanceId: string, name: string, token: string): Promise<LogTail> {
  const encodedName = encodeURIComponent(name)
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/logs/${encodedName}?tail=200`, { headers: authHeaders(token) })
  return readJson<LogTail>(res, `failed to load ${name} for ${instanceId}`)
}

export async function fetchInstanceSettings(instanceId: string, token: string): Promise<InstanceSettings> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/settings`, { headers: authHeaders(token) })
  return readJson<InstanceSettings>(res, `failed to load settings for ${instanceId}`)
}

export async function patchInstanceSettings(instanceId: string, token: string, patch: SettingsPatch): Promise<InstanceSettings> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/settings`, {
    method: 'PATCH',
    headers: { ...authHeaders(token), 'content-type': 'application/json' },
    body: JSON.stringify(patch)
  })
  return readJson<InstanceSettings>(res, `failed to update settings for ${instanceId}`)
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd nanobot-webui && npm test -- src/client/api.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add nanobot-webui/src/client/api.ts nanobot-webui/src/client/api.test.ts
git commit -m "feat(webui): add admin API client helpers"
```

## Task 2: Overview Status Panel

**Files:**
- Create: `nanobot-webui/src/client/components/OverviewPanel.vue`
- Create: `nanobot-webui/src/client/components/OverviewPanel.test.ts`

- [ ] **Step 1: Write the failing component tests**

Create `nanobot-webui/src/client/components/OverviewPanel.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OverviewPanel from './OverviewPanel.vue'

describe('OverviewPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads status cards for enabled instances', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ status: 'ok', model: 'gpt-4.1', provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: ['websocket'], websocket: { enabled: true } })
      })
    )

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('gpt-4.1'))
    expect(wrapper.text()).toContain('openai')
    expect(wrapper.text()).toContain('websocket')
    expect(wrapper.text()).toContain('45s')
  })

  it('shows disabled and failing instances as degraded cards', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, json: vi.fn() }))

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', enabled: false }
        ]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('failed to load status for alpha: 502'))
    expect(wrapper.text()).toContain('beta')
    expect(wrapper.text()).toContain('disabled')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd nanobot-webui && npm test -- src/client/components/OverviewPanel.test.ts`

Expected: FAIL because `OverviewPanel.vue` does not exist.

- [ ] **Step 3: Implement `OverviewPanel.vue`**

Create `nanobot-webui/src/client/components/OverviewPanel.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { fetchInstanceStatus, type InstanceStatus, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

type StatusEntry = {
  instance: PublicInstance
  status?: InstanceStatus
  error?: string
}

const entries = ref<StatusEntry[]>([])

function formatUptime(value?: number) {
  if (typeof value !== 'number') return 'unknown uptime'
  if (value < 60) return `${Math.round(value)}s`
  return `${Math.round(value / 60)}m`
}

async function loadStatuses() {
  const loaded = await Promise.all(
    props.instances.map(async (instance): Promise<StatusEntry> => {
      if (!instance.enabled) return { instance, error: 'disabled' }
      try {
        return { instance, status: await fetchInstanceStatus(instance.id, props.token) }
      } catch (err) {
        return { instance, error: err instanceof Error ? err.message : String(err) }
      }
    })
  )
  entries.value = loaded
}

onMounted(loadStatuses)
watch(() => [props.token, props.instances], loadStatuses, { deep: true })
</script>

<template>
  <section class="panel overview-panel">
    <div class="panel-heading">
      <div>
        <h2>Overview</h2>
        <p>{{ instances.length }} configured instances</p>
      </div>
      <button class="secondary compact" type="button" @click="loadStatuses">Refresh</button>
    </div>
    <div class="status-grid">
      <article v-for="entry in entries" :key="entry.instance.id" class="status-card" :class="{ 'is-degraded': entry.error }">
        <div class="status-title">
          <strong>{{ entry.instance.name }}</strong>
          <span>{{ entry.error ? 'degraded' : entry.status?.status || 'loading' }}</span>
        </div>
        <p v-if="entry.error" class="error-text">{{ entry.error }}</p>
        <dl v-else>
          <div><dt>Model</dt><dd>{{ entry.status?.model || 'unknown' }}</dd></div>
          <div><dt>Provider</dt><dd>{{ entry.status?.resolved_provider || entry.status?.provider || 'unknown' }}</dd></div>
          <div><dt>Channels</dt><dd>{{ entry.status?.channels?.join(', ') || 'none' }}</dd></div>
          <div><dt>Websocket</dt><dd>{{ entry.status?.websocket?.enabled ? 'enabled' : 'disabled' }}</dd></div>
          <div><dt>Uptime</dt><dd>{{ formatUptime(entry.status?.uptime_s) }}</dd></div>
        </dl>
      </article>
    </div>
  </section>
</template>

<style scoped>
.overview-panel { min-height: 24rem; }
.panel-heading { display: flex; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
.panel-heading p { color: #69778c; margin: 0.25rem 0 0; }
.compact { min-height: 2.2rem; padding: 0 0.8rem; }
.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.85rem; }
.status-card { border: 1px solid #dce4ef; border-radius: 0.85rem; background: #fbfdff; padding: 1rem; }
.status-card.is-degraded { border-color: #fed7aa; background: #fff7ed; }
.status-title { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.status-title span { border-radius: 999px; background: #dcfce7; color: #166534; font-size: 0.75rem; font-weight: 800; padding: 0.2rem 0.55rem; text-transform: uppercase; }
.is-degraded .status-title span { background: #ffedd5; color: #9a3412; }
dl { display: grid; gap: 0.5rem; margin: 1rem 0 0; }
dl div { display: flex; justify-content: space-between; gap: 1rem; }
dt { color: #69778c; }
dd { margin: 0; text-align: right; }
.error-text { color: #9a3412; line-height: 1.5; }
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd nanobot-webui && npm test -- src/client/components/OverviewPanel.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add nanobot-webui/src/client/components/OverviewPanel.vue nanobot-webui/src/client/components/OverviewPanel.test.ts
git commit -m "feat(webui): add instance overview panel"
```

## Task 3: Multi-Instance Chat Bridge

**Files:**
- Modify: `nanobot-webui/src/server/chatBridge.ts`
- Modify: `nanobot-webui/src/server/chatBridge.test.ts`

- [ ] **Step 1: Write failing bridge tests**

Append to `describe('registerChatBridge', () => { ... })` in `nanobot-webui/src/server/chatBridge.test.ts`:

```ts
  it('connects multiple enabled upstream websockets for group chat', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'alpha-ws-secret', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', adminToken: 'admin-secret', websocketToken: 'beta-ws-secret', enabled: true }
        ]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_group', { instanceIds: ['alpha', 'beta'] })

    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2))
    expect(FakeWebSocket.instances.map((item) => item.url)).toEqual([
      'ws://nanobot-alpha:8765/?client_id=nanobot-webui&token=alpha-ws-secret',
      'ws://nanobot-beta:8765/?client_id=nanobot-webui&token=beta-ws-secret'
    ])
  })

  it('broadcasts group messages only to connected open upstreams', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'alpha-ws-secret', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', adminToken: 'admin-secret', websocketToken: 'beta-ws-secret', enabled: true }
        ]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_group', { instanceIds: ['alpha', 'beta'] })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2))
    socket.emit('send_group_message', { text: 'hello group' })

    expect(FakeWebSocket.instances[0].sent).toEqual([JSON.stringify({ text: 'hello group' })])
    expect(FakeWebSocket.instances[1].sent).toEqual([JSON.stringify({ text: 'hello group' })])
  })

  it('labels group chat events by upstream instance', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'alpha-ws-secret', enabled: true }]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_group', { instanceIds: ['alpha'] })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].emit('message', Buffer.from('{"event":"delta","chat_id":"c1","text":"hi"}'))

    await expect(waitForEvent(socket, 'chat_event')).resolves.toEqual({ instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'hi' })
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd nanobot-webui && npm test -- src/server/chatBridge.test.ts`

Expected: FAIL because `connect_group` and `send_group_message` are not implemented.

- [ ] **Step 3: Implement group upstream management**

In `nanobot-webui/src/server/chatBridge.ts`, change the connection handler to keep a `Map<string, WebSocketLike>` and add `connect_group` and `send_group_message`. Preserve `connect_instance` and `send_message` as single-instance compatibility wrappers.

Use this replacement for the `namespace.on('connection', ...)` block:

```ts
  namespace.on('connection', (socket) => {
    const upstreams = new Map<string, WebSocketLike>()
    let generation = 0

    function closeAll() {
      generation++
      for (const upstream of upstreams.values()) upstream.close()
      upstreams.clear()
    }

    function connectInstances(instanceIds: string[]) {
      closeAll()
      const currentGeneration = generation
      const uniqueIds = [...new Set(instanceIds.filter(Boolean))]
      for (const instanceId of uniqueIds) {
        const instance = config.instances.find((item) => item.id === instanceId)
        if (!instance) {
          socket.emit('chat_event', { instanceId, event: 'error', chatId: '', detail: 'unknown instance' })
          continue
        }
        if (!instance.enabled) {
          socket.emit('chat_event', { instanceId, event: 'error', chatId: '', detail: 'instance disabled' })
          continue
        }
        try {
          const upstream = new WebSocketImpl(websocketUrlForInstance(instance))
          upstreams.set(instanceId, upstream)
          socket.emit('chat_event', { instanceId, event: 'chat.connecting', chatId: '' })
          upstream.on('message', (data) => {
            if (currentGeneration !== generation) return
            socket.emit('chat_event', normalizeNanobotEvent(instanceId, data.toString()))
          })
          upstream.on('close', () => {
            if (currentGeneration !== generation) return
            upstreams.delete(instanceId)
            socket.emit('chat_event', { instanceId, event: 'chat.disconnected', chatId: '' })
          })
          upstream.on('error', () => {
            if (currentGeneration !== generation) return
            socket.emit('chat_event', { instanceId, event: 'chat.connection_failed', chatId: '' })
          })
        } catch {
          socket.emit('chat_event', { instanceId, event: 'error', chatId: '', detail: 'chat.connection_failed' })
        }
      }
    }

    socket.on('connect_group', (payload: unknown) => {
      const instanceIds = payload && typeof payload === 'object' ? (payload as { instanceIds?: unknown }).instanceIds : undefined
      if (!Array.isArray(instanceIds) || !instanceIds.every((item) => typeof item === 'string')) {
        socket.emit('chat_event', invalidConnectPayload())
        return
      }
      connectInstances(instanceIds)
    })

    socket.on('connect_instance', (payload: unknown) => {
      if (!payload || typeof payload !== 'object') {
        socket.emit('chat_event', invalidConnectPayload())
        return
      }
      const { instanceId } = payload as { instanceId?: unknown }
      if (typeof instanceId !== 'string' || !instanceId) {
        socket.emit('chat_event', invalidConnectPayload(typeof instanceId === 'string' ? instanceId : ''))
        return
      }
      connectInstances([instanceId])
    })

    socket.on('send_group_message', (payload) => {
      for (const upstream of upstreams.values()) {
        if (upstream.readyState === WebSocket.OPEN) upstream.send(JSON.stringify(payload))
      }
    })

    socket.on('send_message', (payload) => {
      for (const upstream of upstreams.values()) {
        if (upstream.readyState === WebSocket.OPEN) upstream.send(JSON.stringify(payload))
      }
    })

    socket.on('disconnect', closeAll)
  })
```

- [ ] **Step 4: Run bridge tests**

Run: `cd nanobot-webui && npm test -- src/server/chatBridge.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add nanobot-webui/src/server/chatBridge.ts nanobot-webui/src/server/chatBridge.test.ts
git commit -m "feat(webui): support multi-instance chat bridge"
```

## Task 4: Group Chat UI

**Files:**
- Modify: `nanobot-webui/src/client/socket.ts`
- Modify: `nanobot-webui/src/client/components/ChatPanel.vue`
- Create: `nanobot-webui/src/client/components/ChatPanel.test.ts`

- [ ] **Step 1: Write failing component tests**

Create `nanobot-webui/src/client/components/ChatPanel.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { EventEmitter } from 'node:events'
import { describe, expect, it, vi } from 'vitest'
import ChatPanel from './ChatPanel.vue'

class FakeSocket extends EventEmitter {
  emitted: Array<{ event: string; payload: unknown }> = []
  emit(event: string, payload?: unknown) {
    this.emitted.push({ event, payload })
    return super.emit(event, payload)
  }
  disconnect = vi.fn()
}

describe('ChatPanel', () => {
  it('connects selected instances and broadcasts messages', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://beta', enabled: true }
        ]
      }
    })

    await wrapper.get('input[value="alpha"]').setValue(true)
    await wrapper.get('input[value="beta"]').setValue(true)
    await wrapper.get('[data-testid="connect-group"]').trigger('click')
    await wrapper.get('textarea').setValue('hello group')
    await wrapper.get('form').trigger('submit')

    expect(socket.emitted).toContainEqual({ event: 'connect_group', payload: { instanceIds: ['alpha', 'beta'] } })
    expect(socket.emitted).toContainEqual({ event: 'send_group_message', payload: { text: 'hello group' } })
  })

  it('renders labeled transcript events', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }]
      }
    })

    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'streamed reply' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('alpha')
    expect(wrapper.text()).toContain('streamed reply')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd nanobot-webui && npm test -- src/client/components/ChatPanel.test.ts`

Expected: FAIL because `ChatPanel` does not accept `token` or `createSocket` and has no group chat controls.

- [ ] **Step 3: Implement typed socket helper**

Replace `nanobot-webui/src/client/socket.ts` with:

```ts
import { io, type Socket } from 'socket.io-client'

export type ChatEvent = {
  instanceId: string
  event: string
  chatId: string
  text?: string
  detail?: string
}

export type ChatSocket = Pick<Socket, 'on' | 'emit' | 'disconnect'>

export function createChatSocket(token: string): ChatSocket {
  return io('/chat', { auth: { token } })
}
```

- [ ] **Step 4: Implement group chat panel**

Replace `nanobot-webui/src/client/components/ChatPanel.vue` with a component that accepts `token`, `instances`, and optional `createSocket`, tracks selected instance IDs, emits `connect_group` and `send_group_message`, and renders transcript entries.

The component must include these stable test hooks:

```vue
<button data-testid="connect-group" type="button" @click="connectGroup">Connect selected</button>
<form @submit.prevent="sendMessage">
  <textarea v-model="message" placeholder="Message all selected instances"></textarea>
</form>
```

Use `socket.on('chat_event', (event: ChatEvent) => transcript.value.push(event))` to append responses and `socket.disconnect()` in `onUnmounted`.

- [ ] **Step 5: Run component tests**

Run: `cd nanobot-webui && npm test -- src/client/components/ChatPanel.test.ts`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add nanobot-webui/src/client/socket.ts nanobot-webui/src/client/components/ChatPanel.vue nanobot-webui/src/client/components/ChatPanel.test.ts
git commit -m "feat(webui): add group chat panel"
```

## Task 5: Logs Panel

**Files:**
- Create: `nanobot-webui/src/client/components/LogsPanel.vue`
- Create: `nanobot-webui/src/client/components/LogsPanel.test.ts`

- [ ] **Step 1: Write failing tests**

Create `nanobot-webui/src/client/components/LogsPanel.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import LogsPanel from './LogsPanel.vue'

describe('LogsPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads logs and renders selected tail', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ logs: [{ name: 'nanobot.log' }] }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ name: 'nanobot.log', lines: ['line one', 'line two'] }) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(LogsPanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('nanobot.log'))
    await wrapper.get('button[data-log="nanobot.log"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('line two'))
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd nanobot-webui && npm test -- src/client/components/LogsPanel.test.ts`

Expected: FAIL because `LogsPanel.vue` does not exist.

- [ ] **Step 3: Implement `LogsPanel.vue`**

Create a read-only panel with an instance selector, log list buttons with `data-log="<name>"`, and a `<pre>` for tail lines. Use `fetchInstanceLogs` on selected instance change and `fetchLogTail` on log button click.

- [ ] **Step 4: Run tests**

Run: `cd nanobot-webui && npm test -- src/client/components/LogsPanel.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add nanobot-webui/src/client/components/LogsPanel.vue nanobot-webui/src/client/components/LogsPanel.test.ts
git commit -m "feat(webui): add logs panel"
```

## Task 6: Settings Panel

**Files:**
- Create: `nanobot-webui/src/client/components/SettingsPanel.vue`
- Create: `nanobot-webui/src/client/components/SettingsPanel.test.ts`

- [ ] **Step 1: Write failing tests**

Create `nanobot-webui/src/client/components/SettingsPanel.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SettingsPanel from './SettingsPanel.vue'

describe('SettingsPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads settings and patches model/provider', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ agent: { model: 'old', provider: 'auto', resolved_provider: 'openai', has_api_key: true }, requires_restart: false }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ agent: { model: 'new', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: true }) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(SettingsPanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect(wrapper.get('input[name="model"]').element.value).toBe('old'))
    await wrapper.get('input[name="model"]').setValue('new')
    await wrapper.get('input[name="provider"]').setValue('openai')
    await wrapper.get('form').trigger('submit')

    await vi.waitFor(() => expect(wrapper.text()).toContain('Restart required'))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/instances/alpha/settings', expect.objectContaining({ method: 'PATCH' }))
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd nanobot-webui && npm test -- src/client/components/SettingsPanel.test.ts`

Expected: FAIL because `SettingsPanel.vue` does not exist.

- [ ] **Step 3: Implement `SettingsPanel.vue`**

Create a panel with an enabled-instance selector, model input named `model`, provider input named `provider`, submit button, current resolved provider, has API key status, and restart warning when `requires_restart` is true. Use `fetchInstanceSettings` and `patchInstanceSettings`.

- [ ] **Step 4: Run tests**

Run: `cd nanobot-webui && npm test -- src/client/components/SettingsPanel.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add nanobot-webui/src/client/components/SettingsPanel.vue nanobot-webui/src/client/components/SettingsPanel.test.ts
git commit -m "feat(webui): add settings panel"
```

## Task 7: App Tab Integration

**Files:**
- Modify: `nanobot-webui/src/client/App.vue`
- Modify: `nanobot-webui/src/client/App.test.ts`

- [ ] **Step 1: Write failing tab integration test**

Append to `nanobot-webui/src/client/App.test.ts`:

```ts
  it('shows dashboard tabs after login', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')

    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))
    expect(wrapper.text()).toContain('Group Chat')
    expect(wrapper.text()).toContain('Logs')
    expect(wrapper.text()).toContain('Settings')
  })
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd nanobot-webui && npm test -- src/client/App.test.ts`

Expected: FAIL because tabs are not implemented.

- [ ] **Step 3: Implement tabs in `App.vue`**

Import `OverviewPanel`, `LogsPanel`, and `SettingsPanel`. Add `const activeTab = ref<'overview' | 'chat' | 'logs' | 'settings'>('overview')`. Render a tab bar after dashboard header and conditionally render:

```vue
<OverviewPanel v-if="activeTab === 'overview'" :token="token" :instances="instances" />
<ChatPanel v-else-if="activeTab === 'chat'" :token="token" :instances="instances" />
<LogsPanel v-else-if="activeTab === 'logs'" :token="token" :instances="instances" />
<SettingsPanel v-else :token="token" :instances="instances" />
```

Keep `InstanceList` visible as a side rail on desktop if it does not crowd the tab content; otherwise show it above tabs on mobile through CSS.

- [ ] **Step 4: Run App tests**

Run: `cd nanobot-webui && npm test -- src/client/App.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add nanobot-webui/src/client/App.vue nanobot-webui/src/client/App.test.ts
git commit -m "feat(webui): add dashboard navigation tabs"
```

## Task 8: Full Verification

**Files:**
- Inspect generated files under `nanobot-webui/`.

- [ ] **Step 1: Run full webui verification**

Run:

```bash
cd nanobot-webui && npm test && npm run build && docker compose -f docker-compose.example.yml config && npx tsc -p tsconfig.server.json --noEmit && npx tsc --noEmit
```

Expected: all commands exit 0.

- [ ] **Step 2: Run Docker runtime smoke**

Run:

```bash
cd nanobot-webui && docker build -t nanobot-webui:full-dashboard-smoke . && docker run --rm nanobot-webui:full-dashboard-smoke node -e "import('./dist/server/index.js').then(() => console.log('server import ok'))"
```

Expected: `server import ok`.

- [ ] **Step 3: Remove generated artifacts**

Run:

```bash
git status --short
```

If `nanobot-webui/tsconfig.tsbuildinfo` appears, delete only that generated file.

- [ ] **Step 4: Final commit if verification modified only expected source files**

Run:

```bash
git status --short
```

Expected: no generated build artifacts are staged or untracked. Existing `.superpowers/` scratch files may remain untracked and must not be committed.

## Self-Review

- Spec coverage: group chat is covered by Tasks 3 and 4; status overview by Task 2; logs by Task 5; settings by Task 6; navigation by Task 7; verification by Task 8.
- Placeholder scan: the plan uses concrete file paths, commands, expected failures, expected passes, and commit messages. It intentionally leaves component styling details to implementation within already-defined admin-console patterns, while behavior and test hooks are explicit.
- Type consistency: `PublicInstance`, `InstanceStatus`, `LogInfo`, `LogTail`, `InstanceSettings`, `ChatEvent`, and `ChatSocket` names are introduced before use in later tasks.
