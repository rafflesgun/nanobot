<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Icon } from '@iconify/vue'
import CodeEditor from './CodeEditor.vue'
import { fetchStateInstances, saveStateInstances, type PublicInstance, type StateInstance } from '../api'

const props = withDefaults(defineProps<{
  token?: string
  instances: PublicInstance[]
  loadInstances?: typeof fetchStateInstances
  saveInstances?: typeof saveStateInstances
}>(), {
  token: '',
  loadInstances: () => fetchStateInstances,
  saveInstances: () => saveStateInstances
})

const emit = defineEmits<{
  'instances-changed': [instances: PublicInstance[]]
}>()

type LocalInstance = StateInstance & { persisted?: boolean }

const localInstances = ref<LocalInstance[]>(props.instances.map((instance) => ({ ...instance, persisted: true })))
const editingId = ref('')
const id = ref('')
const name = ref('')
const baseUrl = ref('')
const adminToken = ref('')
const websocketUrl = ref('')
const websocketToken = ref('')
const editMode = ref<'gui' | 'json'>('gui')
const jsonDraft = ref('')
const jsonError = ref('')

function slug(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

function resetForm() {
  editingId.value = ''
  id.value = ''
  name.value = ''
  baseUrl.value = ''
  adminToken.value = ''
  websocketUrl.value = ''
  websocketToken.value = ''
}

function saveInstance() {
  const nextId = editingId.value || slug(id.value || name.value)
  if (!nextId || !name.value.trim() || !baseUrl.value.trim()) return
  const existing = localInstances.value.find((instance) => instance.id === nextId)
  if (existing) {
    existing.name = name.value.trim()
    existing.baseUrl = baseUrl.value.trim()
    if (adminToken.value) existing.adminToken = adminToken.value
    if (websocketUrl.value) existing.websocketUrl = websocketUrl.value
    if (websocketToken.value) existing.websocketToken = websocketToken.value
  } else {
    localInstances.value.push({ id: nextId, name: name.value.trim(), baseUrl: baseUrl.value.trim(), adminToken: adminToken.value, websocketUrl: websocketUrl.value, websocketToken: websocketToken.value, enabled: true, persisted: false })
  }
  persistInstances()
  resetForm()
}

function editInstance(instance: LocalInstance) {
  editingId.value = instance.id
  id.value = instance.id
  name.value = instance.name
  baseUrl.value = instance.baseUrl
  adminToken.value = ''
  websocketUrl.value = ''
  websocketToken.value = ''
}

function toggleInstance(instance: LocalInstance) {
  instance.enabled = !instance.enabled
  persistInstances()
}

function deleteInstance(instanceId: string) {
  localInstances.value = localInstances.value.filter((instance) => instance.id !== instanceId)
  persistInstances()
}

function persistInstances() {
  if (!props.token) return
  void props.saveInstances(props.token, localInstances.value).then((saved) => {
    const publicInstances = Array.isArray(saved) ? saved : localInstances.value.map(({ persisted, adminToken, websocketUrl, websocketToken, ...rest }) => rest)
    emit('instances-changed', publicInstances)
  }).catch(() => {
    const publicInstances = localInstances.value.map(({ persisted, adminToken, websocketUrl, websocketToken, ...rest }) => rest)
    emit('instances-changed', publicInstances)
  })
}

function selectMode(mode: 'gui' | 'json') {
  if (mode === 'json') {
    jsonDraft.value = JSON.stringify(localInstances.value.map((i) => {
      const obj: Record<string, unknown> = { id: i.id, name: i.name, baseUrl: i.baseUrl, enabled: i.enabled }
      if (i.adminToken) obj.adminToken = i.adminToken
      if (i.websocketUrl) obj.websocketUrl = i.websocketUrl
      if (i.websocketToken) obj.websocketToken = i.websocketToken
      return obj
    }), null, 2)
  }
  jsonError.value = ''
  editMode.value = mode
}

function saveJsonInstances() {
  jsonError.value = ''
  let parsed: any[]
  try {
    parsed = JSON.parse(jsonDraft.value)
  } catch {
    jsonError.value = 'Invalid JSON'
    return
  }
  if (!Array.isArray(parsed)) {
    jsonError.value = 'JSON must be an array'
    return
  }
  for (const entry of parsed) {
    if (!entry.id || !entry.name || !entry.baseUrl) {
      jsonError.value = `Instance "${entry.id || '(missing id)'}" missing required field (id, name, baseUrl)`
      return
    }
  }
  localInstances.value = parsed.map((entry: any) => ({
    id: entry.id,
    name: entry.name,
    baseUrl: entry.baseUrl,
    adminToken: entry.adminToken ?? '',
    websocketToken: entry.websocketToken ?? '',
    enabled: entry.enabled ?? true,
    persisted: localInstances.value.some((li) => li.id === entry.id)
  }))
  persistInstances()
}

onMounted(() => {
  if (!props.token) return
  void props.loadInstances(props.token).then((instances) => {
    if (!Array.isArray(instances) || instances.length === 0) return
    const configIds = new Set(props.instances.map((i) => i.id))
    const stateIds = new Set(instances.map((i) => i.id))
    const merged = [
      ...props.instances.map((i) => {
        const stateVersion = instances.find((s) => s.id === i.id)
        return { ...(stateVersion ?? i), persisted: true }
      }),
      ...instances.filter((s) => !configIds.has(s.id)).map((i) => ({ ...i, persisted: true }))
    ]
    localInstances.value = merged
  }).catch(() => {})
})
</script>

<template>
  <section class="panel instances-panel">
    <div class="panel-heading">
      <div>
        <h2>Agents</h2>
        <p>Manage agent instance connections to the dashboard.</p>
      </div>
    </div>

    <div class="mode-toggle" data-testid="instances-toolbar">
      <button type="button" data-mode="gui" :class="{ active: editMode === 'gui' }" @click="selectMode('gui')">
        <Icon icon="mdi:form-textbox" :width="14" /> GUI Form
      </button>
      <button type="button" data-mode="json" :class="{ active: editMode === 'json' }" @click="selectMode('json')">
        <Icon icon="mdi:code-json" :width="14" /> JSON
      </button>
    </div>

    <div v-if="editMode === 'gui'" class="instances-layout">
      <form class="instance-form" @submit.prevent="saveInstance">
        <label>
          <span>ID</span>
          <input v-model="id" :disabled="!!editingId" type="text" placeholder="beta">
        </label>
        <label>
          <span>Name</span>
          <input data-testid="new-instance-name" v-model="name" type="text" placeholder="Beta">
        </label>
        <label>
          <span>Admin base URL</span>
          <input data-testid="new-instance-url" v-model="baseUrl" type="text" placeholder="http://nanobot-beta:18790">
        </label>
        <label>
          <span>Admin token</span>
          <input data-testid="new-instance-admin-token" v-model="adminToken" type="password" autocomplete="off">
        </label>
        <label>
          <span>WebSocket URL</span>
          <input data-testid="new-instance-ws-url" v-model="websocketUrl" type="text" placeholder="ws://nanobot-beta:8765">
        </label>
        <label>
          <span>WebSocket token</span>
          <input data-testid="new-instance-ws-token" v-model="websocketToken" type="password" autocomplete="off">
        </label>
        <button data-testid="create-instance" type="button" class="btn btn-primary" @click="saveInstance">
          <Icon :icon="editingId ? 'mdi:content-save-outline' : 'mdi:plus'" :width="14" /> {{ editingId ? 'Save instance' : 'Create instance' }}
        </button>
      </form>

      <div class="instance-cards">
        <article v-for="instance in localInstances" :key="instance.id" class="instance-card">
          <header>
            <div class="instance-meta">
              <label class="toggle">
                <input type="checkbox" :data-testid="`toggle-${instance.id}`" :checked="instance.enabled" @change="toggleInstance(instance)">
                <span class="toggle-slider"></span>
              </label>
              <div>
                <strong>{{ instance.name }}</strong>
                <span class="instance-id">{{ instance.id }}</span>
              </div>
            </div>
          </header>
          <p class="instance-url">{{ instance.baseUrl }}</p>
          <div class="instance-actions">
            <button class="btn btn-ghost compact" type="button" :data-testid="`edit-${instance.id}`" @click="editInstance(instance)">
              <Icon icon="mdi:pencil-outline" :width="13" /> Edit
            </button>
            <button class="btn btn-danger-ghost compact" type="button" :data-testid="`delete-${instance.id}`" @click="deleteInstance(instance.id)">
              <Icon icon="mdi:delete-outline" :width="13" /> Delete
            </button>
          </div>
        </article>
        <p v-if="localInstances.length === 0" class="muted empty">No instances configured yet.</p>
      </div>
    </div>

    <div v-else-if="editMode === 'json'" class="json-editor-panel">
      <p v-if="jsonError" class="error-text" role="alert">{{ jsonError }}</p>
      <CodeEditor
        v-model="jsonDraft"
        data-testid="instances-json-editor"
        language="json"
        placeholder="[]"
      />
      <button type="button" data-testid="save-json-instances" class="btn btn-primary" @click="saveJsonInstances">
        <Icon icon="mdi:content-save-outline" :width="14" /> Save All Instances
      </button>
    </div>
  </section>
</template>

<style scoped>
.panel-heading { margin-bottom: 1rem; }
.panel-heading p { color: var(--muted); line-height: 1.5; margin: 0.25rem 0 0; }
.mode-toggle { display: inline-flex; gap: 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; margin-bottom: 0.75rem; }
.mode-toggle button { display: inline-flex; align-items: center; gap: 5px; padding: 0.35rem 0.75rem; font-size: 12px; font-weight: 560; cursor: pointer; border: none; background: var(--surface); color: var(--muted); transition: all 0.15s; }
.mode-toggle button + button { border-left: 1px solid var(--border); }
.mode-toggle button.active { background: oklch(64% 0.18 255 / 0.18); color: var(--fg); }
.mode-toggle button:hover:not(.active) { background: var(--surface-2); }
.instances-layout { display: grid; grid-template-columns: minmax(18rem, 0.8fr) minmax(22rem, 1.2fr); gap: 1rem; }
.instance-form, .instance-card { border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88); padding: 1rem; }
.instance-form { display: grid; gap: 0.85rem; align-content: start; }
.instance-form label { display: grid; gap: 0.4rem; }
.instance-form span { color: var(--fg); font-size: 12px; font-weight: 700; }
.instance-form input { font-size: 13px; }
.instance-cards { display: grid; gap: 0.5rem; }
.instance-card { display: grid; gap: 0.6rem; padding: 0.85rem 1rem; }
.instance-card header { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; }
.instance-meta { display: flex; align-items: center; gap: 10px; }
.instance-meta strong { font-size: 14px; }
.instance-id { color: var(--muted); font-size: 11px; font-family: var(--font-mono); }
.instance-url { color: var(--muted); margin: 0; font-size: 12px; font-family: var(--font-mono); }
.instance-actions { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.json-editor-panel { display: grid; gap: 0.75rem; }
.error-text { color: var(--warn); margin: 0; line-height: 1.5; }
.muted { color: var(--muted); }
.empty { text-align: center; padding: 2rem 0; font-size: 13px; }
.toggle { position: relative; display: inline-block; width: 36px; height: 20px; flex-shrink: 0; cursor: pointer; }
.toggle input { opacity: 0; width: 0; height: 0; position: absolute; }
.toggle-slider { position: absolute; inset: 0; border-radius: 20px; background: oklch(40% 0.02 255); border: 1px solid var(--border); transition: all 0.2s ease; }
.toggle-slider::before { content: ''; position: absolute; width: 14px; height: 14px; left: 2px; bottom: 2px; border-radius: 50%; background: var(--muted); transition: all 0.2s ease; }
.toggle input:checked + .toggle-slider { background: oklch(64% 0.18 255 / 0.25); border-color: oklch(64% 0.18 255 / 0.5); }
.toggle input:checked + .toggle-slider::before { transform: translateX(16px); background: oklch(72% 0.16 255); }
.toggle input:focus-visible + .toggle-slider { outline: 2px solid var(--accent); outline-offset: 2px; }
@media (max-width: 900px) { .instances-layout { grid-template-columns: 1fr; } }
</style>
