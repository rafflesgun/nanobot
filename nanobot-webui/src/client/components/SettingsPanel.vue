<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchInstanceSettings, patchInstanceSettings, type InstanceSettings, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

const selectedInstanceId = ref('')
const settings = ref<InstanceSettings | null>(null)
const model = ref('')
const provider = ref('')
const error = ref('')
const mode = ref<'gui' | 'json' | 'markdown'>('gui')
const jsonDraft = ref('')
const loading = ref(false)
const saving = ref(false)
let loadSequence = 0
let saveSequence = 0

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))
const selectedInstance = computed(() => enabledInstances.value.find((instance) => instance.id === selectedInstanceId.value))
const settingsSnapshot = computed<InstanceSettings | null>(() => settings.value
  ? { ...settings.value, agent: { ...settings.value.agent, model: model.value, provider: provider.value } }
  : null)
const markdownSummary = computed(() => {
  const snapshot = settingsSnapshot.value
  if (!snapshot) return 'No settings loaded.'
  return [
    `Model: \`${snapshot.agent.model || 'unset'}\``,
    `Provider: \`${snapshot.agent.provider || 'unset'}\``,
    `Resolved provider: \`${snapshot.agent.resolved_provider || 'unknown'}\``,
    `API key: \`${snapshot.agent.has_api_key ? 'configured' : 'missing'}\``
  ].join('\n')
})

function selectMode(nextMode: 'gui' | 'json' | 'markdown') {
  if (nextMode === 'json' && settingsSnapshot.value) {
    jsonDraft.value = JSON.stringify(settingsSnapshot.value, null, 2)
  }
  mode.value = nextMode
}

async function loadSettings() {
  const instance = selectedInstance.value
  const sequence = ++loadSequence
  settings.value = null
  model.value = ''
  provider.value = ''
  jsonDraft.value = ''
  error.value = ''
  if (saving.value) {
    saveSequence++
    saving.value = false
  }

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
    jsonDraft.value = JSON.stringify(loaded, null, 2)
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
  const loadSnapshot = loadSequence
  error.value = ''
  let patch = { model: model.value, provider: provider.value }
  if (mode.value === 'json') {
    try {
      const parsed = JSON.parse(jsonDraft.value) as InstanceSettings
      if (typeof parsed?.agent?.model !== 'string' || typeof parsed?.agent?.provider !== 'string') {
        throw new Error('missing agent model or provider')
      }
      patch = { model: parsed.agent.model, provider: parsed.agent.provider }
    } catch (err) {
      error.value = `Invalid JSON${err instanceof Error ? `: ${err.message}` : ''}`
      return
    }
  }
  saving.value = true
  try {
    const updated = await patchInstanceSettings(instance.id, props.token, patch)
    if (sequence !== saveSequence || loadSnapshot !== loadSequence) return
    settings.value = updated
    model.value = updated.agent.model
    provider.value = updated.agent.provider
    jsonDraft.value = JSON.stringify(updated, null, 2)
  } catch (err) {
    if (sequence !== saveSequence || loadSnapshot !== loadSequence) return
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
        <div class="settings-toolbar" data-testid="settings-toolbar">
          <button type="button" data-mode="gui" :class="{ active: mode === 'gui' }" @click="selectMode('gui')">GUI Form</button>
          <button type="button" data-mode="json" :class="{ active: mode === 'json' }" @click="selectMode('json')">JSON</button>
          <button type="button" data-mode="markdown" :class="{ active: mode === 'markdown' }" @click="selectMode('markdown')">Markdown</button>
        </div>
        <p v-if="!settings" class="empty-state">Settings editor is available after loading completes.</p>
        <template v-else-if="mode === 'gui'">
          <label>
            <span>Model</span>
            <input v-model="model" name="model" type="text" autocomplete="off">
          </label>
          <label>
            <span>Provider</span>
            <input v-model="provider" name="provider" type="text" autocomplete="off">
          </label>
        </template>
        <textarea v-else-if="mode === 'json'" v-model="jsonDraft" data-testid="settings-json" class="settings-json" spellcheck="false" />
        <pre v-else data-testid="settings-markdown" class="settings-markdown">{{ markdownSummary }}</pre>
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
  color: #93a4bd;
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
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.85rem;
  background: rgba(8, 13, 28, 0.72);
  padding: 1rem;
}

.settings-form label {
  display: grid;
  gap: 0.45rem;
}

.settings-toolbar {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-start;
}

.settings-toolbar button {
  border-color: rgba(148, 163, 184, 0.28);
  background: rgba(15, 23, 42, 0.72);
}

.settings-toolbar button.active {
  border-color: rgba(56, 189, 248, 0.62);
  background: rgba(14, 165, 233, 0.18);
  color: #e0f2fe;
}

.instance-select span,
.settings-form span {
  color: #cbd5e1;
  font-weight: 700;
}

.settings-json,
.settings-markdown {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  background: rgba(2, 6, 23, 0.62);
  color: #dbeafe;
  font: 0.88rem/1.6 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  margin: 0;
  min-height: 14rem;
  padding: 0.85rem;
  white-space: pre-wrap;
}

.settings-json {
  resize: vertical;
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
  color: #93a4bd;
}

dd {
  margin: 0;
  text-align: right;
}

.error-text {
  color: #fdba74;
  line-height: 1.5;
  margin: 0;
}

.restart-warning {
  border: 1px solid rgba(251, 146, 60, 0.45);
  border-radius: 0.75rem;
  background: rgba(67, 20, 7, 0.38);
  color: #fdba74;
  font-weight: 800;
  margin: 0;
  padding: 0.8rem 0.95rem;
}
</style>
