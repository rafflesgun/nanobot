<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../../api'

const props = defineProps<{
  name: string
  members: PublicInstance[]
  connectionStatuses: Record<string, 'idle' | 'connecting' | 'connected' | 'error' | 'disconnected'>
  sidebarCollapsed: boolean
}>()

const emit = defineEmits<{
  addMember: []
  removeMember: [instanceId: string]
  toggleSidebar: []
}>()

function statusBorderColor(id: string): string {
  const s = props.connectionStatuses[id]
  if (s === 'connected') return 'var(--success, #22c55e)'
  if (s === 'error' || s === 'disconnected') return 'var(--danger)'
  return 'var(--border)'
}
</script>

<template>
  <div class="chat-header">
    <div class="header-left">
      <button class="icon-btn" @click="emit('toggleSidebar')">
        <Icon :icon="sidebarCollapsed ? 'mdi:chevron-right' : 'mdi:chevron-left'" width="18" />
      </button>
      <h3 class="chat-title">{{ name }}</h3>
      <div class="member-avatars">
        <div
          v-for="member in members"
          :key="member.id"
          class="member-avatar"
          :style="{ borderColor: statusBorderColor(member.id) }"
        >
          {{ member.name.charAt(0).toUpperCase() }}
          <button
            class="remove-member"
            @click="emit('removeMember', member.id)"
          >×</button>
        </div>
        <button class="add-member" @click="emit('addMember')">
          <Icon icon="mdi:plus" :width="14" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.chat-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.member-avatars {
  display: flex;
  align-items: center;
  gap: 4px;
}

.member-avatar {
  position: relative;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--border);
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: oklch(40% 0.05 255);
}

.remove-member {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: none;
  background: var(--danger);
  color: #fff;
  font-size: 9px;
  display: none;
  place-items: center;
  cursor: pointer;
  line-height: 1;
}

.member-avatar:hover .remove-member {
  display: grid;
}

.add-member {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px dashed var(--border);
  background: transparent;
  color: var(--muted);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.add-member:hover {
  color: var(--fg);
  border-color: var(--accent);
}

.icon-btn {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.icon-btn:hover {
  color: var(--fg);
  background: var(--surface);
}
</style>
