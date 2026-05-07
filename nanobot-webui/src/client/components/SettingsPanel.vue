<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchInstanceSettings, patchInstanceSettings, type InstanceSettings, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

const selectedInstanceId = ref('')
const settings = ref<InstanceSettings | null>(null)
const model = ref('')
const provider = ref('')
const error = ref('')
const loading = ref(false)
const saving = ref(false)
let loadSequence = 0
let saveSequence = 0

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))
const selectedInstance = computed(() => enabledInstances.value.find((instance) => instance.id === selectedInstanceId.value))

async function loadSettings() {
  const instance = selectedInstance.value
  const sequence = ++loadSequence
  settings.value = null
  model.value = ''
  provider.value = ''
  error.value = ''

  if (!instance) {
    loading.value = false
    return
  }

  loading.value = true
  try {
    const loaded = await fetchInstanceSettings(instance.id, props.token)
    if (sequence !== loadSequence) return
    settings.value = loaded
    model.value = loaded.agent.model
    provider.value = loaded.agent.provider
  } catch (err) {
    if (sequence !== loadSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function saveSettings() {
  const instance = selectedInstance.value
  if (!instance) return

  const sequence = ++saveSequence
  error.value = ''
  saving.value = true
  try {
    const updated = await patchInstanceSettings(instance.id, props.token, { model: model.value, provider: provider.value })
    if (sequence !== saveSequence) return
    settings.value = updated
    model.value = updated.agent.model
    provider.value = updated.agent.provider
  } catch (err) {
    if (sequence !== saveSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === saveSequence) saving.value = false
  }
}

watch(enabledInstances, (instances) => {
  if (instances.some((instance) => instance.id === selectedInstanceId.value)) return
  selectedInstanceId.value = instances[0]?.id ?? ''
}, { immediate: true })

watch([selectedInstanceId, () => props.token], loadSettings, { immediate: true })
</script>

<template>
  <section class="panel settings-panel">
    <div class="panel-heading">
      <div>
        <h2>Settings</h2>
        <p>Update model and provider through the dashboard proxy.</p>
      </div>
    </div>

    <p v-if="enabledInstances.length === 0" class="empty-state">No enabled instances loaded.</p>

    <div v-else class="settings-grid">
      <label class="instance-select">
        <span>Instance</span>
        <select v-model="selectedInstanceId">
          <option v-for="instance in enabledInstances" :key="instance.id" :value="instance.id">
            {{ instance.name }}
          </option>
        </select>
      </label>

      <p v-if="loading" class="empty-state">Loading settings...</p>
      <p v-if="error" class="error-text" role="alert">{{ error }}</p>

      <form class="settings-form" @submit.prevent="saveSettings">
        <label>
          <span>Model</span>
          <input v-model="model" name="model" type="text" autocomplete="off">
        </label>
        <label>
          <span>Provider</span>
          <input v-model="provider" name="provider" type="text" autocomplete="off">
        </label>
        <button type="submit" :disabled="saving || loading">{{ saving ? 'Saving...' : 'Save settings' }}</button>
      </form>

      <dl v-if="settings" class="settings-meta">
        <div><dt>Resolved provider</dt><dd>{{ settings.agent.resolved_provider || 'unknown' }}</dd></div>
        <div><dt>API key</dt><dd>{{ settings.agent.has_api_key ? 'configured' : 'missing' }}</dd></div>
      </dl>

      <p v-if="settings?.requires_restart" class="restart-warning">Restart required</p>
    </div>
  </section>
</template>

<style scoped>
.settings-panel {
  min-height: 24rem;
}

.panel-heading {
  margin-bottom: 1rem;
}

.panel-heading p,
.empty-state {
  color: #69778c;
  line-height: 1.5;
  margin: 0.25rem 0 0;
}

.settings-grid,
.settings-form,
.instance-select {
  display: grid;
  gap: 1rem;
}

.instance-select,
.settings-form,
.settings-meta {
  border: 1px solid #dce4ef;
  border-radius: 0.85rem;
  background: #fbfdff;
  padding: 1rem;
}

.settings-form label {
  display: grid;
  gap: 0.45rem;
}

.instance-select span,
.settings-form span {
  color: #44546a;
  font-weight: 700;
}

button {
  justify-self: start;
}

.settings-meta {
  display: grid;
  gap: 0.5rem;
  margin: 0;
}

.settings-meta div {
  display: flex;
  gap: 1rem;
  justify-content: space-between;
}

dt {
  color: #69778c;
}

dd {
  margin: 0;
  text-align: right;
}

.error-text {
  color: #9a3412;
  line-height: 1.5;
  margin: 0;
}

.restart-warning {
  border: 1px solid #fed7aa;
  border-radius: 0.75rem;
  background: #fff7ed;
  color: #9a3412;
  font-weight: 800;
  margin: 0;
  padding: 0.8rem 0.95rem;
}
</style>
