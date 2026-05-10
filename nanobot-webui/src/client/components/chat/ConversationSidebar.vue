<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Conversation, PublicInstance } from '../../api'
import type { DateGroup } from './useConversations'
import ConversationItem from './ConversationItem.vue'

const props = defineProps<{
  dateGroups: DateGroup[]
  activeId: string | null
  instances: PublicInstance[]
  collapsed: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  newChat: []
  rename: [id: string, newName: string]
  delete: [id: string]
  collapse: []
}>()

const searchQuery = ref('')

function getMembers(conv: Conversation): PublicInstance[] {
  return props.instances.filter((inst) => conv.selectedIds.includes(inst.id))
}

const filteredGroups = computed<DateGroup[]>(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return props.dateGroups

  return props.dateGroups
    .map((group) => ({
      label: group.label,
      conversations: group.conversations.filter((c) =>
        c.name.toLowerCase().includes(q)
      ),
    }))
    .filter((group) => group.conversations.length > 0)
})
</script>

<template>
  <aside v-if="!collapsed" class="sidebar">
    <button class="new-chat-btn" data-testid="new-chat-btn" @click="emit('newChat')">
      <Icon icon="mdi:plus" width="16" />
      New Chat
    </button>

    <div class="search-wrap">
      <Icon icon="mdi:magnify" width="16" class="search-icon" />
      <input
        v-model="searchQuery"
        class="search-input"
        placeholder="Search conversations…"
      />
    </div>

    <div class="conv-list">
      <template v-for="group in filteredGroups" :key="group.label">
        <div class="date-label">{{ group.label }}</div>
        <ConversationItem
          v-for="conv in group.conversations"
          :id="conv.id"
          :key="conv.id"
          :name="conv.name"
          :members="getMembers(conv)"
          :is-active="conv.id === activeId"
          @select="emit('select', conv.id)"
          @rename="(newName) => emit('rename', conv.id, newName)"
          @delete="emit('delete', conv.id)"
        />
      </template>
    </div>
  </aside>

  <button v-else class="expand-btn" @click="emit('collapse')">
    <Icon icon="mdi:chevron-right" width="18" />
  </button>
</template>

<style scoped>
.sidebar {
  width: 280px;
  min-width: 280px;
  border-right: 1px solid var(--border);
  background: oklch(16% 0.012 255 / 0.9);
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: 1px solid oklch(64% 0.18 255 / 0.4);
  border-radius: 8px;
  background: transparent;
  color: var(--accent);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
}

.new-chat-btn:hover {
  background: oklch(64% 0.18 255 / 0.08);
}

.search-wrap {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}

.search-input {
  width: 100%;
  padding: 6px 8px 6px 30px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: oklch(19% 0.014 255 / 0.5);
  color: var(--fg);
  font-size: 0.82rem;
  outline: none;
}

.search-input::placeholder {
  color: var(--muted);
}

.search-input:focus {
  border-color: oklch(64% 0.18 255 / 0.4);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.date-label {
  padding: 6px 8px 2px;
  color: var(--muted);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
}

.expand-btn {
  width: 32px;
  min-width: 32px;
  border-right: 1px solid var(--border);
  background: oklch(16% 0.012 255 / 0.9);
  color: var(--muted);
  border: none;
  border-right: 1px solid var(--border);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.expand-btn:hover {
  color: var(--fg);
}
</style>
