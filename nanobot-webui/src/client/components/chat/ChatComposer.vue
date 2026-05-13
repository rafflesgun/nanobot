<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { ComposerMedia, PublicInstance } from '../../api'
import { extractMentionQuery, isMentionTrigger } from '../../mentionUtils'
import MentionDropdown from './MentionDropdown.vue'
import type { MentionItem } from './MentionDropdown.vue'

const props = defineProps<{
  disabled: boolean
  isGenerating: boolean
  members: PublicInstance[]
  connectionStatuses: Record<string, string>
}>()

const emit = defineEmits<{
  send: [text: string, media: ComposerMedia[], mentionedIds: string[]]
  stop: []
}>()

const message = ref('')
const pendingAttachments = ref<ComposerMedia[]>([])
const textarea = ref<HTMLTextAreaElement | null>(null)
const dropdownRef = ref<InstanceType<typeof MentionDropdown> | null>(null)
const showMentionDropdown = ref(false)
const mentionQuery = ref('')
const mentionStartIndex = ref(-1)

const isMultiline = computed(() => message.value.includes('\n'))

const showMentionHint = computed(() => {
  if (props.members.length < 2) return false
  if (!message.value.trim()) return false
  const hasMention = /(?<=^|[\s])@(\w+)/.test(message.value)
  return !hasMention
})

watch(message, () => {
  nextTick(() => {
    const el = textarea.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 360) + 'px'
  })
})

function handleInput() {
  const el = textarea.value
  if (!el) return
  const pos = el.selectionStart
  const text = message.value
  if (isMentionTrigger(text, pos, text.slice(0, pos))) {
    showMentionDropdown.value = true
    mentionQuery.value = ''
    mentionStartIndex.value = pos - 1
    return
  }
  if (showMentionDropdown.value && mentionStartIndex.value >= 0) {
    const result = extractMentionQuery(text, pos)
    if (result && result.startIndex === mentionStartIndex.value) {
      mentionQuery.value = result.query
    } else {
      showMentionDropdown.value = false
    }
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (showMentionDropdown.value) {
    if (e.key === 'ArrowDown') { e.preventDefault(); dropdownRef.value?.moveDown(); return }
    if (e.key === 'ArrowUp') { e.preventDefault(); dropdownRef.value?.moveUp(); return }
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      if (dropdownRef.value && dropdownRef.value.items.length > 0) {
        dropdownRef.value.confirm()
      }
      return
    }
    if (e.key === 'Escape') { e.preventDefault(); showMentionDropdown.value = false; return }
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function selectMention(item: MentionItem) {
  const name = item.isAll ? 'all' : item.name
  const cursorPos = textarea.value?.selectionStart ?? message.value.length
  const before = message.value.slice(0, mentionStartIndex.value)
  const after = message.value.slice(cursorPos)
  message.value = `${before}@${name} ${after}`
  showMentionDropdown.value = false
  nextTick(() => {
    const el = textarea.value
    if (el) {
      const newPos = before.length + name.length + 2
      el.setSelectionRange(newPos, newPos)
      el.focus()
    }
  })
}

function onBlur() {
  setTimeout(() => { showMentionDropdown.value = false }, 150)
}

function send() {
  const text = message.value.trim()
  if (!text && pendingAttachments.value.length === 0) return
  if (props.disabled || props.isGenerating) return
  emit('send', text, [...pendingAttachments.value], [])
  message.value = ''
  pendingAttachments.value = []
  showMentionDropdown.value = false
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
    <div class="composer-input-wrapper">
      <MentionDropdown
        ref="dropdownRef"
        :members="props.members"
        :connection-statuses="props.connectionStatuses"
        :query="mentionQuery"
        :visible="showMentionDropdown"
        @select="selectMention"
        @close="showMentionDropdown = false"
      />
      <div class="composer-input" :class="{ multiline: isMultiline }">
        <label class="attach-button">
          <Icon icon="mdi:plus-circle-outline" :width="22" />
          <input
            type="file"
            multiple
            data-testid="attachment-input"
            @change="onFileSelect"
          />
        </label>
        <textarea
          ref="textarea"
          v-model="message"
          class="chat-textarea"
          rows="1"
          :placeholder="disabled ? 'Add at least one bot to start chatting' : 'Message...'"
          :disabled="disabled"
          data-testid="chat-input"
          @keydown="handleKeydown"
          @input="handleInput"
          @paste="onPaste"
          @blur="onBlur"
        />
        <button
          v-if="isGenerating"
          class="send-button stop"
          data-testid="stop-button"
          @click="emit('stop')"
        >
          <Icon icon="mdi:stop-circle" :width="20" />
        </button>
        <button
          v-else
          class="send-button"
          :class="{ disabled: disabled || (!message.trim() && !pendingAttachments.length) }"
          data-testid="send-button"
          :disabled="disabled"
          @click="send"
        >
          <Icon icon="mdi:arrow-up" :width="18" />
        </button>
      </div>
    </div>
    <div v-if="showMentionHint" class="mention-hint">
      Mention @all or @AgentName to send
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

.composer-input-wrapper {
  position: relative;
}

.composer-input {
  display: flex;
  align-items: center;
  gap: 0;
  border: 2px solid var(--border);
  border-radius: 24px;
  background: oklch(19% 0.014 255 / 0.88);
  padding: 4px 6px 4px 4px;
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
  padding: 8px 8px;
  resize: none;
  outline: none;
  min-height: 24px;
  max-height: 360px;
}

.chat-textarea::placeholder {
  color: var(--muted);
}

.attach-button {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
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
  flex-shrink: 0;
  border: none;
  border-radius: 50%;
  background: var(--accent);
  color: oklch(99% 0 0);
  cursor: pointer;
  margin-left: 4px;
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

.mention-hint {
  text-align: center;
  font-size: 0.72rem;
  color: var(--muted);
  padding: 4px 0 0;
  opacity: 0.7;
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
