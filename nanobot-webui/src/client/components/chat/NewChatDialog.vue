<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../../api'

const props = defineProps<{
  instances: PublicInstance[]
}>()

const emit = defineEmits<{
  create: [name: string, memberIds: string[]]
  close: []
}>()

const chatName = ref('')
const selectedIds = ref<Set<string>>(new Set())

const enabledInstances = computed(() =>
  props.instances.filter((i) => i.enabled)
)

const canCreate = computed(
  () => chatName.value.trim().length > 0 && selectedIds.value.size > 0
)

function toggleInstance(id: string) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function handleCreate() {
  if (!canCreate.value) return
  emit('create', chatName.value.trim(), [...selectedIds.value])
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') handleCreate()
}
</script>

<template>
  <div class="dialog-backdrop" @click.self="emit('close')">
    <div class="dialog">
      <div class="dialog-header">
        <span class="dialog-title">New Chat</span>
        <button class="close-btn" @click="emit('close')">
          <Icon icon="mdi:close" width="18" />
        </button>
      </div>

      <div class="dialog-body">
        <label class="field-label">Chat name</label>
        <input
          v-model="chatName"
          class="field-input"
          data-testid="new-chat-name"
          placeholder="Enter chat name…"
          @keydown="handleKeydown"
        />

        <label class="field-label">Select bots (min 1)</label>
        <div v-if="enabledInstances.length === 0" class="no-instances">
          No instances available
        </div>
        <div v-else class="instance-list">
          <button
            v-for="inst in enabledInstances"
            :key="inst.id"
            class="instance-option"
            :class="{ selected: selectedIds.has(inst.id) }"
            :data-testid="`select-instance-${inst.id}`"
            @click="toggleInstance(inst.id)"
          >
            <span class="checkbox">{{ selectedIds.has(inst.id) ? '☑' : '☐' }}</span>
            <span>{{ inst.name }}</span>
          </button>
        </div>
      </div>

      <div class="dialog-footer">
        <button class="btn secondary" @click="emit('close')">Cancel</button>
        <button
          class="btn primary"
          data-testid="create-chat"
          :disabled="!canCreate"
          @click="handleCreate"
        >
          Create
        </button>
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
  width: min(440px, 90vw);
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
  display: grid;
  gap: 12px;
}

.field-label {
  font-size: 0.82rem;
  font-weight: 600;
}

.field-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: oklch(14% 0.012 255);
  color: var(--fg);
  font-size: 0.88rem;
  min-height: 40px;
  outline: none;
}

.field-input::placeholder {
  color: var(--muted);
}

.field-input:focus {
  border-color: oklch(64% 0.18 255 / 0.4);
}

.instance-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.instance-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--fg);
  font-size: 0.85rem;
  cursor: pointer;
  text-align: left;
}

.instance-option:hover {
  background: oklch(64% 0.18 255 / 0.05);
}

.instance-option.selected {
  border-color: var(--accent);
  background: oklch(64% 0.18 255 / 0.1);
}

.checkbox {
  flex-shrink: 0;
  font-size: 1rem;
  line-height: 1;
}

.no-instances {
  color: var(--muted);
  font-size: 0.82rem;
  padding: 8px 0;
}

.btn {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
}

.btn.primary {
  background: var(--accent);
  color: white;
  border: none;
}

.btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.secondary {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--fg);
}

.btn.secondary:hover {
  background: var(--surface);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
}
</style>
