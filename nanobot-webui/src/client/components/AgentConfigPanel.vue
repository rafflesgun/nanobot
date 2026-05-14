<script setup lang="ts">
import { ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import CodeEditor from './CodeEditor.vue'
import { fetchInstanceConfig, putInstanceConfig, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instance: PublicInstance | undefined }>()

const config = ref<Record<string, unknown> | null>(null)
const jsonDraft = ref('')
const savedDraft = ref('')
const error = ref('')
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
let loadSequence = 0
let saveSequence = 0

async function loadConfig() {
  const instance = props.instance
  const sequence = ++loadSequence
  config.value = null
  jsonDraft.value = ''
  savedDraft.value = ''
  error.value = ''
  editing.value = false
  if (saving.value) { saveSequence++; saving.value = false }

  if (!instance) { loading.value = false; return }

  loading.value = true
  try {
    const loaded = await fetchInstanceConfig(instance.id, props.token)
    if (sequence !== loadSequence) return
    config.value = loaded
    jsonDraft.value = JSON.stringify(loaded, null, 2)
    savedDraft.value = jsonDraft.value
  } catch (err) {
    if (sequence !== loadSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

function startEditing() {
  editing.value = true
}

function cancelEditing() {
  jsonDraft.value = savedDraft.value
  editing.value = false
  error.value = ''
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
    savedDraft.value = jsonDraft.value
    editing.value = false
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
      <div class="editor-heading">
        <div class="editor-title">
          <Icon icon="mdi:cog-outline" :width="18" class="heading-icon" />
          <strong>Agent Configuration</strong>
          <span class="mode-badge" :class="{ readonly: !editing, editing }">{{ editing ? 'editing' : 'read-only' }}</span>
        </div>
        <div class="editor-actions">
          <template v-if="!editing">
            <button type="button" class="btn btn-primary compact" @click="startEditing">
              <Icon icon="mdi:pencil-outline" :width="14" /> Edit
            </button>
          </template>
          <template v-if="editing">
            <button type="button" class="btn btn-ghost compact" @click="cancelEditing">
              <Icon icon="mdi:close" :width="14" /> Cancel
            </button>
            <button type="button" data-testid="save-agent-config" class="btn btn-primary compact" :disabled="saving" @click="saveConfig">
              <Icon icon="mdi:content-save-outline" :width="14" /> {{ saving ? 'Saving...' : 'Save' }}
            </button>
          </template>
        </div>
      </div>
      <CodeEditor
        v-model="jsonDraft"
        language="json"
        :readOnly="!editing"
        placeholder="{}"
      />
    </template>
  </section>
</template>

<style scoped>
.agent-config-panel { display: grid; gap: 1rem; }
.muted { color: var(--muted); line-height: 1.5; margin: 0; }
.error-text { color: var(--warn); line-height: 1.5; margin: 0; }
.editor-heading { align-items: center; display: flex; justify-content: space-between; gap: 0.75rem; }
.editor-title { display: flex; align-items: center; gap: 8px; }
.editor-title strong { font-size: 14px; }
.heading-icon { color: var(--muted); }
.mode-badge { font-size: 10px; padding: 2px 7px; border-radius: 4px; font-weight: 600; text-transform: uppercase; }
.mode-badge.readonly { background: oklch(50% 0.04 255 / 0.3); color: var(--muted); }
.mode-badge.editing { background: oklch(70% 0.15 145 / 0.15); color: var(--success); }
.editor-actions { display: flex; gap: 0.4rem; }
.btn { display: inline-flex; align-items: center; gap: 5px; border: 1px solid var(--border); border-radius: 7px; background: var(--surface); color: var(--fg); font-size: 12px; font-weight: 560; cursor: pointer; transition: all 0.15s; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn:hover:not(:disabled) { border-color: oklch(64% 0.18 255 / 0.4); }
.compact { min-height: 2rem; padding: 0 0.6rem; }
.btn-primary { border-color: oklch(64% 0.18 255 / 0.5); background: oklch(64% 0.18 255 / 0.15); color: oklch(78% 0.14 255); }
.btn-primary:hover:not(:disabled) { background: oklch(64% 0.18 255 / 0.25); border-color: var(--accent); }
.btn-ghost { border-color: transparent; background: transparent; color: var(--muted); }
.btn-ghost:hover:not(:disabled) { background: var(--surface-2); color: var(--fg); }
</style>
