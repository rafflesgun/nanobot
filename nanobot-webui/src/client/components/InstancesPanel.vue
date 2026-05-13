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

type LocalInstance = StateInstance & { persisted?: boolean }

const localInstances = ref<LocalInstance[]>(props.instances.map((instance) => ({ ...instance, persisted: true })))
const editingId = ref('')
const id = ref('')
const name = ref('')
const baseUrl = ref('')
const adminToken = ref('')
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
    if (websocketToken.value) existing.websocketToken = websocketToken.value
  } else {
    localInstances.value.push({ id: nextId, name: name.value.trim(), baseUrl: baseUrl.value.trim(), adminToken: adminToken.value, websocketToken: websocketToken.value, enabled: true, persisted: false })
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
  void props.saveInstances(props.token, localInstances.value)
}

function selectMode(mode: 'gui' | 'json') {
  if (mode === 'json') {
    jsonDraft.value = JSON.stringify(localInstances.value.map((i) => {
      const obj: Record<string, unknown> = { id: i.id, name: i.name, baseUrl: i.baseUrl, enabled: i.enabled }
      if (i.adminToken) obj.adminToken = i.adminToken
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
    if (!Array.isArray(instances)) return
    localInstances.value = instances.map((instance) => ({ ...instance, persisted: true }))
  }).catch(() => {})
})
</script>

<template>
  <section class="panel instances-panel">
    <div class="panel-heading">
      <div>
        <h2>Instances</h2>
        <p>Manage agent instance connections to the dashboard.</p>
      </div>
    </div>

    <div class="instances-toolbar" data-testid="instances-toolbar">
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
          <span>WebSocket token</span>
          <input data-testid="new-instance-ws-token" v-model="websocketToken" type="password" autocomplete="off">
        </label>
        <button data-testid="create-instance" type="button" @click="saveInstance">{{ editingId ? 'Save instance' : 'Create instance' }}</button>
      </form>

      <div class="instance-cards">
        <article v-for="instance in localInstances" :key="instance.id" class="instance-card">
          <header>
            <div>
              <strong>{{ instance.name }}</strong>
              <span>{{ instance.id }}</span>
            </div>
            <em>{{ instance.enabled ? 'enabled' : 'disabled' }}</em>
          </header>
          <p>{{ instance.baseUrl }}</p>
          <small>{{ instance.persisted ? 'from dashboard state' : 'local draft' }}</small>
          <div class="instance-actions">
            <button class="secondary" type="button" :data-testid="`edit-${instance.id}`" @click="editInstance(instance)">Edit</button>
            <button class="secondary" type="button" :data-testid="`toggle-${instance.id}`" @click="toggleInstance(instance)">{{ instance.enabled ? 'Disable' : 'Enable' }}</button>
            <button class="secondary danger" type="button" :data-testid="`delete-${instance.id}`" @click="deleteInstance(instance.id)">Delete</button>
          </div>
        </article>
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
      <button type="button" data-testid="save-json-instances" @click="saveJsonInstances">Save All Instances</button>
    </div>
  </section>
</template>

<style scoped>
.panel-heading { margin-bottom: 1rem; }
.panel-heading p { color: var(--muted); line-height: 1.5; margin: 0.25rem 0 0; }
.instances-toolbar { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
.instances-toolbar button { display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); color: var(--muted); padding: 0.35rem 0.75rem; font-size: 12px; font-weight: 560; cursor: pointer; }
.instances-toolbar button.active { border-color: var(--accent); background: oklch(64% 0.18 255 / 0.18); color: var(--fg); }
.instances-layout { display: grid; grid-template-columns: minmax(18rem, 0.8fr) minmax(22rem, 1.2fr); gap: 1rem; }
.instance-form,
.instance-card { border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88); padding: 1rem; }
.instance-form { display: grid; gap: 0.85rem; align-content: start; }
.instance-form label { display: grid; gap: 0.4rem; }
.instance-form span { color: var(--fg); font-weight: 700; }
.instance-cards { display: grid; gap: 0.75rem; }
.instance-card { display: grid; gap: 0.75rem; }
.instance-card header { display: flex; justify-content: space-between; gap: 1rem; }
.instance-card header div { display: grid; gap: 0.25rem; }
.instance-card span,
.instance-card p,
.instance-card small { color: var(--muted); margin: 0; }
.instance-card em { border: 1px solid var(--border); border-radius: 999px; color: var(--fg); font-size: 0.75rem; font-style: normal; padding: 0.2rem 0.55rem; }
.instance-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.danger { border-color: oklch(68% 0.17 25 / 0.42); color: oklch(80% 0.12 25); }
.json-editor-panel { display: grid; gap: 0.75rem; }
.error-text { color: var(--warn); margin: 0; line-height: 1.5; }
@media (max-width: 900px) { .instances-layout { grid-template-columns: 1fr; } }
</style>
