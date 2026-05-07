<script setup lang="ts">
import { onMounted, ref } from 'vue'
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
        <p>Local CRUD shell. Server-side persistence will store these in /data in the next slice.</p>
      </div>
    </div>

    <div class="instances-layout">
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
  </section>
</template>

<style scoped>
.panel-heading { margin-bottom: 1rem; }
.panel-heading p { color: #93a4bd; line-height: 1.5; margin: 0.25rem 0 0; }
.instances-layout { display: grid; grid-template-columns: minmax(18rem, 0.8fr) minmax(22rem, 1.2fr); gap: 1rem; }
.instance-form,
.instance-card { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 0.85rem; background: rgba(8, 13, 28, 0.72); padding: 1rem; }
.instance-form { display: grid; gap: 0.85rem; align-content: start; }
.instance-form label { display: grid; gap: 0.4rem; }
.instance-form span { color: #cbd5e1; font-weight: 700; }
.instance-cards { display: grid; gap: 0.75rem; }
.instance-card { display: grid; gap: 0.75rem; }
.instance-card header { display: flex; justify-content: space-between; gap: 1rem; }
.instance-card header div { display: grid; gap: 0.25rem; }
.instance-card span,
.instance-card p,
.instance-card small { color: #93a4bd; margin: 0; }
.instance-card em { border: 1px solid rgba(148, 163, 184, 0.24); border-radius: 999px; color: #dbe7ff; font-size: 0.75rem; font-style: normal; padding: 0.2rem 0.55rem; }
.instance-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.danger { border-color: rgba(248, 113, 113, 0.42); color: #fecaca; }
@media (max-width: 900px) { .instances-layout { grid-template-columns: 1fr; } }
</style>
