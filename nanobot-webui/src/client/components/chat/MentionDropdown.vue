<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../../api'

export type MentionItem = {
  id: string
  name: string
  isAll: boolean
  status?: string
}

const props = defineProps<{
  members: PublicInstance[]
  connectionStatuses: Record<string, string>
  query: string
  visible: boolean
}>()

const emit = defineEmits<{
  select: [item: MentionItem]
  close: []
}>()

const highlightedIndex = ref(0)

const items = computed<MentionItem[]>(() => {
  const result: MentionItem[] = []
  if (props.members.length >= 2) {
    const allMatch = 'all'.includes(props.query.toLowerCase())
    if (allMatch) result.push({ id: '__all__', name: 'all', isAll: true })
  }
  const filtered = props.members.filter(m =>
    m.name.toLowerCase().includes(props.query.toLowerCase())
  )
  for (const m of filtered) {
    result.push({ id: m.id, name: m.name, isAll: false, status: props.connectionStatuses[m.id] })
  }
  return result
})

watch(() => props.query, () => {
  highlightedIndex.value = 0
})

watch(() => props.visible, (v) => {
  if (v) highlightedIndex.value = 0
})

function statusColor(status?: string): string {
  if (status === 'connected') return '#4a7'
  if (status === 'connecting') return '#da3'
  if (status === 'error' || status === 'disconnected') return '#d55'
  return '#666'
}

function avatarColor(name: string): string {
  const colors = ['#5a5aff', '#4a7', '#da3', '#d5a', '#7ad', '#a77']
  let sum = 0
  for (let i = 0; i < name.length; i++) sum += name.charCodeAt(i)
  return colors[sum % colors.length]
}

function moveUp() {
  if (items.value.length === 0) return
  highlightedIndex.value = (highlightedIndex.value - 1 + items.value.length) % items.value.length
}

function moveDown() {
  if (items.value.length === 0) return
  highlightedIndex.value = (highlightedIndex.value + 1) % items.value.length
}

function confirm() {
  const item = items.value[highlightedIndex.value]
  if (item) emit('select', item)
}

defineExpose({ moveUp, moveDown, confirm, items, highlightedIndex })
</script>

<template>
  <div v-if="visible && items.length > 0" class="mention-dropdown">
    <div
      v-for="(item, i) in items"
      :key="item.id"
      class="mention-item"
      :class="{ highlighted: i === highlightedIndex }"
      @click="emit('select', item)"
      @mouseenter="highlightedIndex = i"
    >
      <div v-if="item.isAll" class="mention-avatar all-avatar">
        <Icon icon="mdi:account-group-outline" :width="14" />
      </div>
      <div v-else class="mention-avatar" :style="{ background: avatarColor(item.name) }">
        {{ item.name.charAt(0).toUpperCase() }}
      </div>
      <span class="mention-name">@{{ item.name }}</span>
      <span v-if="item.isAll" class="mention-label">all members</span>
      <span v-else class="mention-status" :style="{ background: statusColor(item.status) }" />
    </div>
  </div>
  <div v-else-if="visible && items.length === 0" class="mention-dropdown empty">
    <span class="no-results">No matching agents</span>
  </div>
</template>

<style scoped>
.mention-dropdown {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  background: oklch(20% 0.014 255);
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 4px;
  max-height: 240px;
  overflow-y: auto;
  z-index: 50;
  box-shadow: 0 -4px 16px oklch(0% 0 0 / 0.4);
}

.mention-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  cursor: pointer;
  transition: background 80ms;
}

.mention-item:first-child {
  border-radius: 10px 10px 0 0;
}

.mention-item:last-child {
  border-radius: 0 0 10px 10px;
}

.mention-item.highlighted {
  background: oklch(30% 0.02 255);
}

.mention-avatar {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

.all-avatar {
  background: oklch(50% 0.12 255);
}

.mention-name {
  font-size: 0.82rem;
  font-weight: 500;
}

.mention-label {
  font-size: 0.72rem;
  color: var(--muted);
  margin-left: auto;
}

.mention-status {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-left: auto;
  flex-shrink: 0;
}

.empty {
  padding: 10px 14px;
}

.no-results {
  font-size: 0.78rem;
  color: var(--muted);
}
</style>
