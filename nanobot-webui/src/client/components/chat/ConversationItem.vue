<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../../api'

const props = defineProps<{
  id: string
  name: string
  members: PublicInstance[]
  isActive: boolean
}>()

const emit = defineEmits<{
  select: []
  rename: [newName: string]
  delete: []
}>()

const isRenaming = ref(false)
const renameValue = ref('')
const renameInput = ref<HTMLInputElement>()

function startRename() {
  renameValue.value = props.name
  isRenaming.value = true
  nextTick(() => renameInput.value?.focus())
}

function confirmRename() {
  const trimmed = renameValue.value.trim()
  if (trimmed && trimmed !== props.name) {
    emit('rename', trimmed)
  }
  isRenaming.value = false
}

function cancelRename() {
  isRenaming.value = false
}

const displayMembers = props.members.slice(0, 3)
const overflowCount = props.members.length - 3
</script>

<template>
  <button
    class="conv-item"
    :class="{ active: isActive }"
    @click="emit('select')"
  >
    <div class="avatar-stack">
      <div
        v-for="(member, i) in displayMembers"
        :key="member.id"
        class="mini-avatar"
        :style="i > 0 ? 'margin-left: -4px' : ''"
      >
        {{ member.name.charAt(0).toUpperCase() }}
      </div>
      <span v-if="overflowCount > 0" class="overflow-text">+{{ overflowCount }}</span>
    </div>

    <input
      v-if="isRenaming"
      ref="renameInput"
      v-model="renameValue"
      class="rename-input"
      @keydown.enter="confirmRename"
      @keydown.escape="cancelRename"
      @blur="confirmRename"
      @click.stop
    />
    <span v-else class="conv-name">{{ name }}</span>

    <div class="action-menu" v-if="!isRenaming">
      <button class="menu-action" @click.stop="startRename" title="Rename">
        <Icon icon="mdi:pencil" width="14" />
      </button>
      <button class="menu-action danger" @click.stop="emit('delete')" title="Delete">
        <Icon icon="mdi:delete-outline" width="14" />
      </button>
    </div>
  </button>
</template>

<style scoped>
.conv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  text-align: left;
  cursor: pointer;
}

.conv-item.active {
  background: oklch(64% 0.18 255 / 0.12);
  border-color: oklch(64% 0.18 255 / 0.25);
  color: var(--fg);
}

.conv-item:hover:not(.active) {
  background: oklch(19% 0.014 255 / 0.5);
}

.avatar-stack {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.mini-avatar {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: oklch(64% 0.18 255);
  color: white;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.overflow-text {
  margin-left: 4px;
  font-size: 0.7rem;
  color: var(--muted);
}

.conv-name {
  flex: 1;
  font-size: 0.82rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rename-input {
  flex: 1;
  padding: 2px 6px;
  border: 1px solid oklch(64% 0.18 255);
  border-radius: 4px;
  background: var(--surface);
  color: var(--fg);
  font-size: 0.82rem;
  outline: none;
}

.action-menu {
  display: none;
  flex-shrink: 0;
}

.conv-item:hover .action-menu {
  display: flex;
  gap: 2px;
}

.menu-action {
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.menu-action:hover {
  background: var(--surface);
}

.menu-action.danger:hover {
  color: var(--danger);
}
</style>
