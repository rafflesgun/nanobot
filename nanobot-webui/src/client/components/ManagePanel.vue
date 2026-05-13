<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../api'
import AgentConfigPanel from './AgentConfigPanel.vue'
import SubagentsPanel from './SubagentsPanel.vue'
import LogsPanel from './LogsPanel.vue'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

type ManageSection = 'agent-config' | 'subagents' | 'logs'

const sections: Array<{ id: ManageSection; label: string; icon: string }> = [
  { id: 'agent-config', label: 'Agent Config', icon: 'mdi:cog-outline' },
  { id: 'subagents', label: 'Subagents', icon: 'mdi:file-document-edit-outline' },
  { id: 'logs', label: 'Logs', icon: 'mdi:file-document-outline' }
]

const enabledInstances = computed(() => props.instances.filter((i) => i.enabled))
const selectedInstanceId = ref('')
const activeSection = ref<ManageSection>('agent-config')
const selectedInstance = computed(() => enabledInstances.value.find((i) => i.id === selectedInstanceId.value))
const restarting = ref(false)

watch(enabledInstances, (instances) => {
  if (instances.some((i) => i.id === selectedInstanceId.value)) return
  selectedInstanceId.value = instances[0]?.id ?? ''
}, { immediate: true })

async function restartInstance() {
  if (!selectedInstance.value) return
  restarting.value = true
  try {
    const res = await fetch(`/api/instances/${encodeURIComponent(selectedInstance.value.id)}/restart`, {
      method: 'POST',
      headers: { authorization: `Bearer ${props.token}` }
    })
    if (!res.ok) throw new Error(`Restart failed: ${res.status}`)
  } catch {
    // Graceful degradation — endpoint may not exist yet
  } finally {
    restarting.value = false
  }
}
</script>

<template>
  <section class="panel manage-panel">
    <div class="manage-layout">
      <div class="manage-sidebar" data-testid="instance-sidebar">
        <div class="sidebar-heading">Instances</div>
        <button
          v-for="instance in enabledInstances"
          :key="instance.id"
          type="button"
          :data-instance="instance.id"
          class="instance-item"
          :class="{ active: instance.id === selectedInstanceId }"
          @click="selectedInstanceId = instance.id"
        >
          <span class="dot success"></span>
          <span class="instance-name">{{ instance.name }}</span>
        </button>
        <p v-if="enabledInstances.length === 0" class="muted">No enabled instances</p>
      </div>

      <div class="manage-main">
        <div class="manage-header">
          <div>
            <h2>{{ selectedInstance?.name ?? 'Select an instance' }}</h2>
            <p v-if="selectedInstance" class="muted">{{ selectedInstance.id }} · {{ selectedInstance.baseUrl }}</p>
          </div>
          <button
            v-if="selectedInstance"
            type="button"
            data-testid="restart-button"
            class="restart-btn"
            :disabled="restarting"
            @click="restartInstance"
          >
            <Icon icon="mdi:restart" :width="16" />
            {{ restarting ? 'Restarting...' : 'Restart' }}
          </button>
        </div>

        <nav class="manage-subnav" aria-label="Manage sections">
          <button
            v-for="section in sections"
            :key="section.id"
            type="button"
            :data-section="section.id"
            :class="{ active: activeSection === section.id }"
            @click="activeSection = section.id"
          >
            <Icon :icon="section.icon" :width="16" />
            {{ section.label }}
          </button>
        </nav>

        <div class="manage-content">
          <AgentConfigPanel v-if="activeSection === 'agent-config'" :token="token" :instance="selectedInstance" />
          <SubagentsPanel v-else-if="activeSection === 'subagents'" :token="token" :instance="selectedInstance" />
          <LogsPanel v-else-if="activeSection === 'logs'" :token="token" :instance="selectedInstance" />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.manage-panel { display: grid; gap: 1rem; }
.manage-layout { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 1rem; }
.manage-sidebar { border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88); padding: 0.75rem; display: grid; gap: 0.4rem; align-content: start; }
.sidebar-heading { color: var(--fg); font-weight: 700; font-size: 13px; margin-bottom: 0.25rem; }
.instance-item { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--muted); text-align: left; cursor: pointer; font-size: 13px; }
.instance-item:hover { background: var(--surface-2); }
.instance-item.active { border-color: oklch(64% 0.18 255 / 0.35); background: oklch(64% 0.18 255 / 0.18); color: var(--fg); }
.instance-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.manage-main { display: grid; gap: 1rem; min-width: 0; }
.manage-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.manage-header h2 { margin: 0; font-size: 16px; }
.manage-header p { margin: 0.15rem 0 0; font-size: 12px; }
.restart-btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); color: var(--fg); font-size: 12px; font-weight: 560; cursor: pointer; }
.restart-btn:hover { border-color: var(--accent); }
.restart-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.manage-subnav { display: flex; gap: 0.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
.manage-subnav button { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--muted); font-size: 12px; font-weight: 560; cursor: pointer; }
.manage-subnav button.active { border-color: oklch(64% 0.18 255 / 0.35); background: oklch(64% 0.18 255 / 0.18); color: var(--fg); }
.manage-content { min-width: 0; }
.muted { color: var(--muted); line-height: 1.5; margin: 0; }
@media (max-width: 900px) { .manage-layout { grid-template-columns: 1fr; } }
</style>
