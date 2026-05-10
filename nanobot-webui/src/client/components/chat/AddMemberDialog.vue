<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../../api'

const props = defineProps<{
  instances: PublicInstance[]
  currentMemberIds: string[]
}>()

const emit = defineEmits<{
  add: [instanceId: string]
  close: []
}>()

const availableInstances = computed(() =>
  props.instances.filter((i) => i.enabled && !props.currentMemberIds.includes(i.id))
)
</script>

<template>
  <div class="dialog-backdrop" @click.self="emit('close')">
    <div class="dialog">
      <div class="dialog-header">
        <span class="dialog-title">Add Bot to Chat</span>
        <button class="close-btn" @click="emit('close')">
          <Icon icon="mdi:close" width="18" />
        </button>
      </div>

      <div class="dialog-body">
        <div v-if="availableInstances.length === 0" class="no-instances">
          All bots are already in this chat
        </div>
        <div v-else class="instance-list">
          <button
            v-for="inst in availableInstances"
            :key="inst.id"
            class="instance-option"
            @click="emit('add', inst.id)"
          >
            <span class="instance-avatar">{{ inst.name.charAt(0).toUpperCase() }}</span>
            <span>{{ inst.name }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: oklch(0% 0 0 / 0.5);
  display: grid;
  place-items: center;
}

.dialog {
  width: min(380px, 90vw);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255);
  box-shadow: 0 20px 60px oklch(0% 0 0 / 0.5);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.dialog-title {
  font-size: 1rem;
  font-weight: 600;
}

.close-btn {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  background: transparent;
  border: none;
  color: var(--muted);
  cursor: pointer;
  border-radius: 6px;
}

.close-btn:hover {
  color: var(--fg);
  background: var(--surface);
}

.dialog-body {
  padding: 16px 20px;
}

.no-instances {
  color: var(--muted);
  font-size: 0.82rem;
  padding: 8px 0;
}

.instance-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.instance-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--fg);
  font-size: 0.88rem;
  cursor: pointer;
  text-align: left;
}

.instance-option:hover {
  background: oklch(64% 0.18 255 / 0.08);
  border-color: var(--accent);
}

.instance-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: oklch(40% 0.05 255);
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  color: #fff;
}
</style>
