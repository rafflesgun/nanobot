<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { deleteSubagent, fetchSubagent, fetchSubagents, saveSubagent, type PublicInstance, type SubagentDetail, type SubagentSummary } from '../api'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

const selectedInstanceId = ref('')
const subagents = ref<SubagentSummary[]>([])
const selected = ref<SubagentDetail | null>(null)
const markdown = ref('')
const newName = ref('')
const error = ref('')
const loading = ref(false)

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))
const canEdit = computed(() => Boolean(selected.value?.editable))

async function loadSubagents() {
  error.value = ''
  selected.value = null
  markdown.value = ''
  if (!selectedInstanceId.value) {
    subagents.value = []
    return
  }
  loading.value = true
  try {
    subagents.value = await fetchSubagents(selectedInstanceId.value, props.token)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
    subagents.value = []
  } finally {
    loading.value = false
  }
}

async function openSubagent(name: string) {
  if (!selectedInstanceId.value) return
  error.value = ''
  try {
    selected.value = await fetchSubagent(selectedInstanceId.value, name, props.token)
    markdown.value = selected.value.content
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function saveCurrent() {
  if (!selectedInstanceId.value) return
  const name = selected.value?.name || newName.value.trim()
  if (!name) {
    error.value = 'Subagent name is required.'
    return
  }
  error.value = ''
  try {
    const saved = await saveSubagent(selectedInstanceId.value, name, props.token, markdown.value)
    selected.value = { ...saved, content: markdown.value }
    await loadSubagents()
    selected.value = { ...saved, content: markdown.value }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function removeSubagent(name: string) {
  if (!selectedInstanceId.value) return
  error.value = ''
  try {
    await deleteSubagent(selectedInstanceId.value, name, props.token)
    await loadSubagents()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

function startNew() {
  const name = newName.value.trim() || 'new-subagent'
  selected.value = { name, description: '', model: '', source: 'workspace', editable: true, content: '' }
  markdown.value = `---\nname: ${name}\ndescription: \n---\n\nDescribe this subagent's instructions.`
}

watch(enabledInstances, (instances) => {
  if (instances.some((instance) => instance.id === selectedInstanceId.value)) return
  selectedInstanceId.value = instances[0]?.id ?? ''
}, { immediate: true })

watch([selectedInstanceId, () => props.token], loadSubagents, { immediate: true })
</script>

<template>
  <section class="subagents-panel">
    <div class="subagents-header">
      <div>
        <h3>Subagents</h3>
        <p>Review built-in agents and edit workspace Markdown subagents.</p>
      </div>
      <select v-model="selectedInstanceId" :disabled="enabledInstances.length === 0">
        <option v-if="enabledInstances.length === 0" value="">No enabled instances</option>
        <option v-for="instance in enabledInstances" :key="instance.id" :value="instance.id">{{ instance.name }}</option>
      </select>
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>
    <p v-if="loading" class="muted">Loading subagents...</p>

    <div class="subagents-layout">
      <div class="subagent-list">
        <div class="new-row">
          <input v-model="newName" data-testid="new-subagent" placeholder="new-subagent" />
          <button type="button" class="secondary compact" @click="startNew">New</button>
        </div>
        <article v-for="item in subagents" :key="item.name" class="subagent-card">
          <div>
            <strong>{{ item.name }}</strong>
            <p>{{ item.description || 'No description' }}</p>
            <small>{{ item.model || 'default model' }} · {{ item.source }}</small>
          </div>
          <div class="subagent-actions">
            <button type="button" class="secondary compact" :data-testid="`edit-${item.name}`" @click="openSubagent(item.name)">Edit</button>
            <button v-if="item.editable" type="button" class="danger compact" :data-testid="`delete-${item.name}`" @click="removeSubagent(item.name)">Delete</button>
          </div>
        </article>
        <p v-if="subagents.length === 0 && !loading" class="muted">No subagents found.</p>
      </div>

      <div class="editor-panel">
        <div class="editor-heading">
          <strong>{{ selected?.name || 'Select a subagent' }}</strong>
          <span v-if="selected">{{ selected.editable ? 'workspace editable' : 'built-in read-only' }}</span>
        </div>
        <textarea
          v-model="markdown"
          data-testid="subagent-markdown"
          :readonly="selected ? !selected.editable : false"
          placeholder="Open a subagent or create a new one to edit Markdown."
        ></textarea>
        <button type="button" data-testid="save-subagent" :disabled="!selected || !canEdit" @click="saveCurrent">Save Markdown</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.subagents-panel { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 0.85rem; background: rgba(8, 13, 28, 0.72); display: grid; gap: 1rem; padding: 1rem; }
.subagents-header { align-items: start; display: flex; justify-content: space-between; gap: 1rem; }
.subagents-header h3 { margin: 0; }
.subagents-header p, .muted { color: #93a4bd; }
.subagents-header p { margin: 0.25rem 0 0; }
.subagents-header select, .new-row input { background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 0.65rem; color: #e5eefb; min-height: 2.25rem; padding: 0 0.7rem; }
.subagents-layout { display: grid; grid-template-columns: minmax(16rem, 0.9fr) minmax(0, 1.2fr); gap: 1rem; }
.subagent-list { display: grid; gap: 0.7rem; align-content: start; }
.new-row { display: flex; gap: 0.5rem; }
.new-row input { flex: 1; min-width: 0; }
.compact { min-height: 2.2rem; padding: 0 0.75rem; }
.subagent-card { align-items: center; border: 1px solid rgba(148, 163, 184, 0.16); border-radius: 0.75rem; background: rgba(15, 23, 42, 0.58); display: flex; justify-content: space-between; gap: 1rem; padding: 0.8rem; }
.subagent-card p { color: #cbd5e1; margin: 0.25rem 0; }
.subagent-card small { color: #93a4bd; }
.subagent-actions { display: flex; gap: 0.45rem; }
.danger { background: rgba(127, 29, 29, 0.45); border-color: rgba(248, 113, 113, 0.4); color: #fecaca; }
.editor-panel { display: grid; gap: 0.75rem; }
.editor-heading { align-items: center; display: flex; justify-content: space-between; gap: 1rem; }
.editor-heading span { color: #93a4bd; font-size: 0.8rem; }
textarea { background: rgba(2, 6, 23, 0.76); border: 1px solid rgba(148, 163, 184, 0.22); border-radius: 0.75rem; color: #e5eefb; font: 0.9rem/1.55 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; min-height: 20rem; padding: 0.85rem; resize: vertical; width: 100%; }
.error-text { color: #fdba74; margin: 0; }
@media (max-width: 960px) { .subagents-layout { grid-template-columns: 1fr; } .subagents-header { flex-direction: column; } }
</style>
