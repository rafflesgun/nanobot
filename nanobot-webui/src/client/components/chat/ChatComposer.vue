<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { ComposerMedia } from '../../api'

const props = defineProps<{
  disabled: boolean
  isGenerating: boolean
}>()

const emit = defineEmits<{
  send: [text: string, media: ComposerMedia[]]
  stop: []
}>()

const message = ref('')
const pendingAttachments = ref<ComposerMedia[]>([])
const textarea = ref<HTMLTextAreaElement | null>(null)

const isMultiline = computed(() => message.value.includes('\n'))

watch(message, () => {
  nextTick(() => {
    const el = textarea.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 360) + 'px'
  })
})

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function send() {
  const text = message.value.trim()
  if (!text && pendingAttachments.value.length === 0) return
  if (props.disabled || props.isGenerating) return
  emit('send', text, [...pendingAttachments.value])
  message.value = ''
  pendingAttachments.value = []
  nextTick(() => {
    const el = textarea.value
    if (el) el.style.height = 'auto'
  })
}

function onFileSelect(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files) return
  for (const file of Array.from(input.files)) {
    const reader = new FileReader()
    reader.onload = () => {
      pendingAttachments.value.push({ data_url: reader.result as string, name: file.name })
    }
    reader.readAsDataURL(file)
  }
  input.value = ''
}

function removeAttachment(index: number) {
  pendingAttachments.value.splice(index, 1)
}

function onPaste(e: ClipboardEvent) {
  const items = e.clipboardData?.items
  if (!items) return
  for (const item of Array.from(items)) {
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const file = item.getAsFile()
      if (!file) continue
      const reader = new FileReader()
      reader.onload = () => {
        pendingAttachments.value.push({ data_url: reader.result as string, name: file.name || 'pasted-image' })
      }
      reader.readAsDataURL(file)
    }
  }
}
</script>

<template>
  <div class="composer">
    <div v-if="pendingAttachments.length" class="attachment-row">
      <span
        v-for="(att, i) in pendingAttachments"
        :key="i"
        class="attachment-chip"
        @click="removeAttachment(i)"
      >
        {{ att.name ?? 'attachment' }} ×
      </span>
    </div>
    <div class="composer-input" :class="{ multiline: isMultiline }">
      <textarea
        ref="textarea"
        v-model="message"
        class="chat-textarea"
        rows="1"
        :placeholder="disabled ? 'Add at least one bot to start chatting' : 'Message... (Enter to send, Shift+Enter for new line)'"
        :disabled="disabled"
        data-testid="chat-input"
        @keydown="handleKeydown"
        @paste="onPaste"
      />
      <div class="composer-actions">
        <label class="attach-button">
          <Icon icon="mdi:plus-circle-outline" :width="22" />
          <input
            type="file"
            multiple
            data-testid="attachment-input"
            @change="onFileSelect"
          />
        </label>
        <button
          v-if="isGenerating"
          class="send-button stop"
          data-testid="stop-button"
          @click="emit('stop')"
        >
          <Icon icon="mdi:stop-circle" :width="22" />
        </button>
        <button
          v-else
          class="send-button"
          :class="{ disabled: disabled || (!message.trim() && !pendingAttachments.length) }"
          data-testid="send-button"
          :disabled="disabled"
          @click="send"
        >
          <Icon icon="mdi:arrow-up" :width="20" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.composer {
  padding: 8px 20px 16px;
  flex-shrink: 0;
}

.attachment-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.attachment-chip {
  display: inline-flex;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 0.75rem;
  color: var(--muted);
  cursor: pointer;
}

.attachment-chip:hover {
  color: var(--fg);
  border-color: var(--accent);
}

.composer-input {
  display: flex;
  align-items: center;
  gap: 4px;
  border: 2px solid var(--border);
  border-radius: 24px;
  background: oklch(19% 0.014 255 / 0.88);
  padding: 6px 8px 6px 4px;
  transition: border-color 150ms;
}

.composer-input:focus-within {
  border-color: var(--accent);
}

.composer-input.multiline {
  border-radius: 16px;
  align-items: flex-end;
}

.chat-textarea {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--fg);
  font-family: inherit;
  font-size: 0.88rem;
  line-height: 1.5;
  padding: 6px 4px 6px 12px;
  resize: none;
  outline: none;
  min-height: 24px;
  max-height: 360px;
}

.chat-textarea::placeholder {
  color: var(--muted);
}

.composer-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.attach-button {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  color: var(--muted);
  cursor: pointer;
}

.attach-button:hover {
  color: var(--fg);
}

.attach-button input {
  display: none;
}

.send-button {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: var(--accent);
  color: oklch(99% 0 0);
  cursor: pointer;
}

.send-button.disabled {
  background: var(--surface-2);
  color: var(--muted);
  cursor: not-allowed;
}

.send-button.stop {
  background: transparent;
  color: var(--danger);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
