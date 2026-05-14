<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import CodeEditor from './CodeEditor.vue'
import { deleteSubagent, fetchSubagent, fetchSubagents, saveSubagent, type PublicInstance, type SubagentDetail, type SubagentSummary } from '../api'

const props = defineProps<{ token: string; instance: PublicInstance | undefined }>()

const subagents = ref<SubagentSummary[]>([])
const selected = ref<SubagentDetail | null>(null)
const markdown = ref('')
const savedMarkdown = ref('')
const newName = ref('')
const error = ref('')
const loading = ref(false)
const editing = ref(false)

const canEdit = computed(() => Boolean(selected.value?.editable))

async function loadSubagents() {
  error.value = ''
  selected.value = null
  markdown.value = ''
  savedMarkdown.value = ''
  editing.value = false
  if (!props.instance) {
    subagents.value = []
    return
  }
  loading.value = true
  try {
    subagents.value = await fetchSubagents(props.instance.id, props.token)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    subagents.value = []
  } finally {
    loading.value = false
  }
}

async function openSubagent(name: string) {
  if (!props.instance) return
  error.value = ''
  editing.value = false
  try {
    selected.value = await fetchSubagent(props.instance.id, name, props.token)
    markdown.value = selected.value.content
    savedMarkdown.value = selected.value.content
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function startEditing() {
  editing.value = true
}

function cancelEditing() {
  markdown.value = savedMarkdown.value
  editing.value = false
}

async function saveCurrent() {
  if (!props.instance) return
  const name = selected.value?.name || newName.value.trim()
  if (!name) {
    error.value = 'Subagent name is required.'
    return
  }
  error.value = ''
  try {
    const saved = await saveSubagent(props.instance.id, name, props.token, markdown.value)
    selected.value = { ...saved, content: markdown.value }
    savedMarkdown.value = markdown.value
    editing.value = false
    await loadSubagents()
    selected.value = { ...saved, content: markdown.value }
    savedMarkdown.value = markdown.value
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeSubagent(name: string) {
  if (!props.instance) return
  error.value = ''
  try {
    await deleteSubagent(props.instance.id, name, props.token)
    await loadSubagents()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function startNew() {
  const name = newName.value.trim() || 'new-subagent'
  selected.value = { name, description: '', model: '', source: 'workspace', editable: true, content: '' }
  const content = `---\nname: ${name}\ndescription: \n---\n\nDescribe this subagent's instructions.`
  markdown.value = content
  savedMarkdown.value = content
  editing.value = true
}

watch(() => props.instance, loadSubagents, { immediate: true })
watch(() => props.token, loadSubagents)
</script>

<template>
  <section class="subagents-panel">
    <div class="subagents-header">
      <div>
        <h3>Subagents</h3>
        <p>Review built-in agents and edit workspace Markdown subagents.</p>
      </div>
    </div>

    <p v-if="!instance" class="muted">Select a target instance above.</p>
    <template v-else>
      <p v-if="error" class="error-text">{{ error }}</p>
      <p v-if="loading" class="muted">Loading subagents...</p>

      <div class="subagents-layout">
        <div class="subagent-list">
          <div class="new-row">
            <input v-model="newName" data-testid="new-subagent" placeholder="new-subagent" />
            <button type="button" class="btn btn-secondary compact" @click="startNew">
              <Icon icon="mdi:plus" :width="14" /> New
            </button>
          </div>
          <article v-for="item in subagents" :key="item.name" class="subagent-card" :class="{ active: selected?.name === item.name }">
            <div class="subagent-info" @click="openSubagent(item.name)">
              <strong>{{ item.name }}</strong>
              <p>{{ item.description || 'No description' }}</p>
              <small>{{ item.model || 'default model' }} · <span class="source-badge" :class="item.source">{{ item.source }}</span></small>
            </div>
            <div class="subagent-actions">
              <button type="button" class="btn btn-ghost compact" :data-testid="`edit-${item.name}`" @click="openSubagent(item.name)">
                <Icon icon="mdi:eye-outline" :width="14" />
              </button>
              <button v-if="item.editable" type="button" class="btn btn-danger-ghost compact" :data-testid="`delete-${item.name}`" @click="removeSubagent(item.name)">
                <Icon icon="mdi:delete-outline" :width="14" />
              </button>
            </div>
          </article>
          <p v-if="subagents.length === 0 && !loading" class="muted">No subagents found.</p>
        </div>

        <div class="editor-panel">
          <div class="editor-heading">
            <div class="editor-title">
              <Icon icon="mdi:file-document-outline" :width="18" class="heading-icon" />
              <strong>{{ selected?.name || 'Select a subagent' }}</strong>
              <span v-if="selected" class="mode-badge" :class="{ readonly: !editing, editing }">{{ editing ? 'editing' : selected.editable ? 'read-only' : 'built-in' }}</span>
            </div>
            <div v-if="selected" class="editor-actions">
              <template v-if="!editing && canEdit">
                <button type="button" class="btn btn-primary compact" @click="startEditing">
                  <Icon icon="mdi:pencil-outline" :width="14" /> Edit
                </button>
              </template>
              <template v-if="editing">
                <button type="button" class="btn btn-ghost compact" @click="cancelEditing">
                  <Icon icon="mdi:close" :width="14" /> Cancel
                </button>
                <button type="button" data-testid="save-subagent" class="btn btn-primary compact" @click="saveCurrent">
                  <Icon icon="mdi:content-save-outline" :width="14" /> Save
                </button>
              </template>
            </div>
          </div>
          <CodeEditor
            v-model="markdown"
            data-testid="subagent-markdown"
            language="markdown"
            :readOnly="!editing"
            placeholder="Select a subagent to view its content."
          />
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.subagents-panel { border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88); display: grid; gap: 1rem; padding: 1rem; }
.subagents-header { align-items: start; display: flex; justify-content: space-between; gap: 1rem; }
.subagents-header h3 { margin: 0; }
.subagents-header p, .muted { color: var(--muted); }
.subagents-header p { margin: 0.25rem 0 0; }
.subagents-layout { display: grid; grid-template-columns: minmax(16rem, 0.9fr) minmax(0, 1.2fr); gap: 1rem; }
.subagent-list { display: grid; gap: 0.5rem; align-content: start; }
.new-row { display: flex; gap: 0.5rem; }
.new-row input { flex: 1; min-width: 0; }
.subagent-card { align-items: center; border: 1px solid var(--border); border-radius: 0.75rem; background: var(--surface-2); display: flex; justify-content: space-between; gap: 0.75rem; padding: 0.7rem 0.8rem; cursor: default; transition: border-color 0.15s; }
.subagent-card.active { border-color: oklch(64% 0.18 255 / 0.5); background: oklch(64% 0.18 255 / 0.08); }
.subagent-card:hover { border-color: oklch(64% 0.18 255 / 0.3); }
.subagent-info { flex: 1; min-width: 0; cursor: pointer; }
.subagent-info strong { font-size: 13px; }
.subagent-card p { color: var(--muted); margin: 0.2rem 0 0; font-size: 12px; }
.subagent-card small { color: var(--muted); font-size: 11px; }
.source-badge { padding: 1px 5px; border-radius: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase; }
.source-badge.workspace { background: oklch(64% 0.18 255 / 0.15); color: oklch(72% 0.14 255); }
.source-badge.builtin { background: oklch(50% 0.04 255 / 0.3); color: var(--muted); }
.subagent-actions { display: flex; gap: 0.3rem; flex-shrink: 0; }
.editor-panel { display: grid; gap: 0.75rem; }
.editor-heading { align-items: center; display: flex; justify-content: space-between; gap: 0.75rem; }
.editor-title { display: flex; align-items: center; gap: 8px; }
.editor-title strong { font-size: 14px; }
.heading-icon { color: var(--muted); }
.mode-badge { font-size: 10px; padding: 2px 7px; border-radius: 4px; font-weight: 600; text-transform: uppercase; }
.mode-badge.readonly { background: oklch(50% 0.04 255 / 0.3); color: var(--muted); }
.mode-badge.editing { background: oklch(70% 0.15 145 / 0.15); color: var(--success); }
.editor-actions { display: flex; gap: 0.4rem; }
.btn-secondary { color: var(--muted); }
.error-text { color: var(--warn); margin: 0; }
@media (max-width: 960px) { .subagents-layout { grid-template-columns: 1fr; } .subagents-header { flex-direction: column; } }
</style>
