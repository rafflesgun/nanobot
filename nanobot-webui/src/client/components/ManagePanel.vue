<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PublicInstance } from '../api'
import LogsPanel from './LogsPanel.vue'
import SettingsPanel from './SettingsPanel.vue'
import SubagentsPanel from './SubagentsPanel.vue'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

type ManageSection = 'settings' | 'subagents' | 'logs' | 'session' | 'memory' | 'credentials' | 'restart'

const sections: Array<{ id: ManageSection; label: string; unsupported?: string }> = [
  { id: 'settings', label: 'Settings' },
  { id: 'subagents', label: 'Subagents' },
  { id: 'logs', label: 'Logs' },
  { id: 'session', label: 'Session', unsupported: 'Session management requires nanobot session API support. Active sessions will appear here when available.' },
  { id: 'memory', label: 'Memory', unsupported: 'Memory management requires nanobot memory API support. Memory snapshots and compaction controls will appear here.' },
  { id: 'credentials', label: 'Credentials', unsupported: 'Credential management requires nanobot credentials API support. API keys and tokens will be managed here.' },
  { id: 'restart', label: 'Restart', unsupported: 'Restart controls require nanobot lifecycle API support. Safe restart and status checks will appear here.' }
]

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))
const selectedInstanceId = ref('')
const activeSection = ref<ManageSection>('settings')
const selectedInstance = computed(() => enabledInstances.value.find((instance) => instance.id === selectedInstanceId.value))
const activeUnsupported = computed(() => sections.find((section) => section.id === activeSection.value)?.unsupported)

watch(enabledInstances, (instances) => {
  if (instances.some((instance) => instance.id === selectedInstanceId.value)) return
  selectedInstanceId.value = instances[0]?.id ?? ''
}, { immediate: true })
</script>

<template>
  <section class="panel manage-panel">
    <div class="manage-header">
      <div>
        <h2>Manage</h2>
        <p>Choose one target instance, then work through the management sections.</p>
      </div>
      <label class="target-select">
        <span>Target instance</span>
        <select v-model="selectedInstanceId">
          <option v-for="instance in enabledInstances" :key="instance.id" :value="instance.id">{{ instance.name }}</option>
        </select>
      </label>
    </div>

    <div class="manage-layout">
      <nav class="manage-subnav" aria-label="Manage sections">
        <button
          v-for="section in sections"
          :key="section.id"
          type="button"
          :data-section="section.id"
          :class="{ active: activeSection === section.id }"
          @click="activeSection = section.id"
        >
          {{ section.label }}
        </button>
      </nav>

      <div class="manage-content">
        <SettingsPanel v-if="activeSection === 'settings'" :token="token" :instance="selectedInstance" />
        <SubagentsPanel v-else-if="activeSection === 'subagents'" :token="token" :instance="selectedInstance" />
        <LogsPanel v-else-if="activeSection === 'logs'" :token="token" :instance="selectedInstance" />
        <article v-else class="unsupported-panel">
          <div class="card-head">
            <div><h3>{{ sections.find((section) => section.id === activeSection)?.label }}</h3></div>
            <span class="pill"><span class="dot warn"></span>coming soon</span>
          </div>
          <p>{{ activeUnsupported }}</p>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.manage-panel { display: grid; gap: 1rem; }
.manage-header { align-items: end; display: flex; justify-content: space-between; gap: 1rem; }
.manage-header p { color: var(--muted); line-height: 1.5; margin: 0.25rem 0 0; }
.target-select { display: grid; gap: 0.45rem; min-width: 16rem; }
.target-select span { color: var(--fg); font-weight: 700; }
.manage-layout { display: grid; grid-template-columns: 12rem minmax(0, 1fr); gap: 1rem; }
.manage-subnav { border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88); display: grid; gap: 0.5rem; align-content: start; padding: 0.75rem; }
.manage-subnav button { background: transparent; border-color: transparent; color: var(--muted); justify-content: start; text-align: left; }
.manage-subnav button.active { background: oklch(64% 0.18 255 / 0.18); border-color: oklch(64% 0.18 255 / 0.35); color: var(--fg); }
.manage-content { min-width: 0; }
.unsupported-panel { border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88); padding: 1rem; }
.card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-block-end: 14px; }
.card-head h3 { margin: 0; font-size: 14px; font-weight: 650; letter-spacing: -0.01em; }
.dot.warn { background: var(--warn); }
.unsupported-panel p { color: var(--muted); line-height: 1.5; }
@media (max-width: 900px) { .manage-header { align-items: stretch; flex-direction: column; } .manage-layout { grid-template-columns: 1fr; } }
</style>
