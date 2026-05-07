<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { PublicInstance } from '../api'
import LogsPanel from './LogsPanel.vue'
import SettingsPanel from './SettingsPanel.vue'
import SubagentsPanel from './SubagentsPanel.vue'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

type ManageSection = 'settings' | 'subagents' | 'logs' | 'usage' | 'costing' | 'session' | 'memory' | 'restart'

const sections: Array<{ id: ManageSection; label: string; unsupported?: string }> = [
  { id: 'settings', label: 'Settings' },
  { id: 'subagents', label: 'Subagents' },
  { id: 'logs', label: 'Logs' },
  { id: 'usage', label: 'Usage' },
  { id: 'costing', label: 'Costing' },
  { id: 'session', label: 'Session', unsupported: 'Session API is not available yet' },
  { id: 'memory', label: 'Memory', unsupported: 'Memory API is not available yet' },
  { id: 'restart', label: 'Restart', unsupported: 'Restart API is not available yet' }
]

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))
const selectedInstanceId = ref('')
const activeSection = ref<ManageSection>('settings')
const selectedInstances = computed(() => enabledInstances.value.filter((instance) => instance.id === selectedInstanceId.value))
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
        <SettingsPanel v-if="activeSection === 'settings'" :token="token" :instances="selectedInstances" />
        <SubagentsPanel v-else-if="activeSection === 'subagents'" :token="token" :instances="selectedInstances" />
        <LogsPanel v-else-if="activeSection === 'logs'" :token="token" :instances="selectedInstances" />
        <article v-else-if="activeSection === 'usage' || activeSection === 'costing'" class="unsupported-panel">
          <h3>{{ sections.find((section) => section.id === activeSection)?.label }}</h3>
          <p>Token accounting is available on the Overview dashboard. Pricing is not configured; showing token usage only.</p>
        </article>
        <article v-else class="unsupported-panel">
          <h3>{{ sections.find((section) => section.id === activeSection)?.label }}</h3>
          <p>{{ activeUnsupported }}</p>
          <small>This section is part of the complete dashboard shell. It will become active when nanobot exposes the matching admin API.</small>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.manage-panel { display: grid; gap: 1rem; }
.manage-header { align-items: end; display: flex; justify-content: space-between; gap: 1rem; }
.manage-header p { color: #93a4bd; line-height: 1.5; margin: 0.25rem 0 0; }
.target-select { display: grid; gap: 0.45rem; min-width: 16rem; }
.target-select span { color: #cbd5e1; font-weight: 700; }
.manage-layout { display: grid; grid-template-columns: 12rem minmax(0, 1fr); gap: 1rem; }
.manage-subnav { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 0.85rem; background: rgba(8, 13, 28, 0.72); display: grid; gap: 0.5rem; align-content: start; padding: 0.75rem; }
.manage-subnav button { background: transparent; border-color: transparent; color: #94a3b8; justify-content: start; text-align: left; }
.manage-subnav button.active { background: rgba(37, 99, 235, 0.2); border-color: rgba(96, 165, 250, 0.42); color: #dbeafe; }
.manage-content { min-width: 0; }
.unsupported-panel { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 0.85rem; background: rgba(8, 13, 28, 0.72); padding: 1rem; }
.unsupported-panel h3 { color: #f8fbff; margin: 0 0 0.5rem; }
.unsupported-panel p,
.unsupported-panel small { color: #93a4bd; line-height: 1.5; }
@media (max-width: 900px) { .manage-header { align-items: stretch; flex-direction: column; } .manage-layout { grid-template-columns: 1fr; } }
</style>
