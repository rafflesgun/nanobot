<script setup lang="ts">
import { ref, watch } from 'vue'
import CodeEditor from './CodeEditor.vue'
import { fetchInstanceSettings, patchInstanceSettings, type InstanceSettings, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instance: PublicInstance | undefined }>()

const settings = ref<InstanceSettings | null>(null)
const jsonDraft = ref('')
const error = ref('')
const loading = ref(false)
const saving = ref(false)
let loadSequence = 0
let saveSequence = 0

async function loadSettings() {
  const instance = props.instance
  const sequence = ++loadSequence
  settings.value = null
  jsonDraft.value = ''
  error.value = ''
  if (saving.value) { saveSequence++; saving.value = false }

  if (!instance) { loading.value = false; return }

  loading.value = true
  try {
    const loaded = await fetchInstanceSettings(instance.id, props.token)
    if (sequence !== loadSequence) return
    settings.value = loaded
    jsonDraft.value = JSON.stringify(loaded, null, 2)
  } catch (err) {
    if (sequence !== loadSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function saveSettings() {
  const instance = props.instance
  if (!instance) return

  const sequence = ++saveSequence
  const loadSnapshot = loadSequence
  error.value = ''

  let patch: { model: string; provider: string }
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

  saving.value = true
  try {
    const updated = await patchInstanceSettings(instance.id, props.token, patch)
    if (sequence !== saveSequence || loadSnapshot !== loadSequence) return
    settings.value = updated
    jsonDraft.value = JSON.stringify(updated, null, 2)
  } catch (err) {
    if (sequence !== saveSequence || loadSnapshot !== loadSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === saveSequence) saving.value = false
  }
}

watch(() => props.instance, loadSettings, { immediate: true })
watch(() => props.token, loadSettings)
</script>

<template>
  <section class="agent-config-panel">
    <p v-if="!instance" class="muted">No target instance selected.</p>
    <p v-if="loading" class="muted">Loading settings...</p>
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>

    <template v-if="settings">
      <CodeEditor
        v-model="jsonDraft"
        language="json"
        placeholder="{}"
      />
      <button type="button" data-testid="save-agent-config" :disabled="saving || loading" @click="saveSettings">{{ saving ? 'Saving...' : 'Save Config' }}</button>

      <dl class="settings-meta">
        <div><dt>Resolved provider</dt><dd>{{ settings.agent.resolved_provider || 'unknown' }}</dd></div>
        <div><dt>API key</dt><dd>{{ settings.agent.has_api_key ? 'configured' : 'missing' }}</dd></div>
      </dl>

      <p v-if="settings.requires_restart" class="restart-warning">Restart required</p>
    </template>
  </section>
</template>

<style scoped>
.agent-config-panel { display: grid; gap: 1rem; }
.muted { color: var(--muted); line-height: 1.5; margin: 0; }
.error-text { color: var(--warn); line-height: 1.5; margin: 0; }
button { justify-self: start; }
.settings-meta { border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88); padding: 1rem; display: grid; gap: 0.5rem; margin: 0; }
.settings-meta div { display: flex; gap: 1rem; justify-content: space-between; }
dt { color: var(--muted); }
dd { margin: 0; text-align: right; }
.restart-warning { border: 1px solid oklch(78% 0.14 85 / 0.45); border-radius: 0.75rem; background: oklch(78% 0.14 85 / 0.12); color: var(--warn); font-weight: 800; margin: 0; padding: 0.8rem 0.95rem; }
</style>
