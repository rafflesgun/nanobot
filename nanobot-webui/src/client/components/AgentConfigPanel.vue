<script setup lang="ts">
import { ref, watch } from 'vue'
import CodeEditor from './CodeEditor.vue'
import { fetchInstanceConfig, putInstanceConfig, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instance: PublicInstance | undefined }>()

const config = ref<Record<string, unknown> | null>(null)
const jsonDraft = ref('')
const error = ref('')
const loading = ref(false)
const saving = ref(false)
let loadSequence = 0
let saveSequence = 0

async function loadConfig() {
  const instance = props.instance
  const sequence = ++loadSequence
  config.value = null
  jsonDraft.value = ''
  error.value = ''
  if (saving.value) { saveSequence++; saving.value = false }

  if (!instance) { loading.value = false; return }

  loading.value = true
  try {
    const loaded = await fetchInstanceConfig(instance.id, props.token)
    if (sequence !== loadSequence) return
    config.value = loaded
    jsonDraft.value = JSON.stringify(loaded, null, 2)
  } catch (err) {
    if (sequence !== loadSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function saveConfig() {
  const instance = props.instance
  if (!instance) return

  const sequence = ++saveSequence
  const loadSnapshot = loadSequence
  error.value = ''

  let parsed: Record<string, unknown>
  try {
    parsed = JSON.parse(jsonDraft.value)
  } catch (err) {
    error.value = `Invalid JSON${err instanceof Error ? `: ${err.message}` : ''}`
    return
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    error.value = 'Config must be a JSON object'
    return
  }

  saving.value = true
  try {
    const updated = await putInstanceConfig(instance.id, props.token, parsed)
    if (sequence !== saveSequence || loadSnapshot !== loadSequence) return
    config.value = updated
    jsonDraft.value = JSON.stringify(updated, null, 2)
  } catch (err) {
    if (sequence !== saveSequence || loadSnapshot !== loadSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === saveSequence) saving.value = false
  }
}

watch(() => props.instance, loadConfig, { immediate: true })
watch(() => props.token, loadConfig)
</script>

<template>
  <section class="agent-config-panel">
    <p v-if="!instance" class="muted">No target instance selected.</p>
    <p v-if="loading" class="muted">Loading config...</p>
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>

    <template v-if="config">
      <CodeEditor
        v-model="jsonDraft"
        language="json"
        placeholder="{}"
      />
      <button type="button" data-testid="save-agent-config" :disabled="saving || loading" @click="saveConfig">{{ saving ? 'Saving...' : 'Save Config' }}</button>
    </template>
  </section>
</template>

<style scoped>
.agent-config-panel { display: grid; gap: 1rem; }
.muted { color: var(--muted); line-height: 1.5; margin: 0; }
.error-text { color: var(--warn); line-height: 1.5; margin: 0; }
button { justify-self: start; }
</style>
