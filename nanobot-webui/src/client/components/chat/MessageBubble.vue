<script setup lang="ts">
import { ref, computed } from 'vue'
import type { TranscriptEntry } from '../../chatTranscript'
import type { PublicInstance } from '../../api'
import { renderMarkdown } from './markdown'
import CodeBlock from './CodeBlock.vue'
import ToolCallBlock from './ToolCallBlock.vue'
import { Icon } from '@iconify/vue'

const props = defineProps<{
  entry: TranscriptEntry
  instance?: PublicInstance
}>()

const copied = ref(false)

const isUser = computed(() => props.entry.role === 'user')
const isTool = computed(() => props.entry.kind === 'tool')
const isReasoning = computed(() => props.entry.kind === 'reasoning')
const isSystem = computed(() => props.entry.role === 'system' && !isTool.value && !isReasoning.value)
const isEmpty = computed(() => !props.entry.text.trim())

function isStreaming(): boolean {
  return props.entry.text.endsWith('▍')
}

function displayText(): string {
  if (isStreaming()) return props.entry.text.slice(0, -1)
  return props.entry.text
}

function avatarLabel(): string {
  const name = props.instance?.name ?? ''
  return name ? name.charAt(0).toUpperCase() : '?'
}

function avatarColor(): string {
  const colors = ['#5a5aff', '#4a7', '#da3', '#d5a', '#7ad', '#a77']
  const id = props.entry.instanceId
  let sum = 0
  for (let i = 0; i < id.length; i++) sum += id.charCodeAt(i)
  return colors[sum % colors.length]
}

async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}

async function copyMarkdown() {
  await copyToClipboard(props.entry.text)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

function decodeHtmlEntities(html: string): string {
  const txt = document.createElement('textarea')
  txt.innerHTML = html
  return txt.value
}

function parsedBlocks(): Array<{ type: 'html' | 'code'; content: string; language: string; rawCode: string }> {
  const html = renderMarkdown(displayText())
  const regex = /<pre class="hljs"><code class="language-(\w+)">([\s\S]*?)<\/code><\/pre>/g
  const blocks: Array<{ type: 'html' | 'code'; content: string; language: string; rawCode: string }> = []
  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = regex.exec(html)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: 'html', content: html.slice(lastIndex, match.index), language: '', rawCode: '' })
    }
    const language = match[1]
    const rawCode = decodeHtmlEntities(match[2])
    blocks.push({ type: 'code', content: match[0], language, rawCode })
    lastIndex = regex.lastIndex
  }
  if (lastIndex < html.length) {
    blocks.push({ type: 'html', content: html.slice(lastIndex), language: '', rawCode: '' })
  }
  return blocks
}
</script>

<template>
  <div v-if="!isEmpty" class="message" :class="{ 'is-user': isUser }">
    <div v-if="isUser" class="user-bubble">
      <div class="bubble-header">
        <div class="user-avatar">Y</div>
        <span class="bubble-name">You</span>
      </div>
      <div class="bubble-content">{{ displayText() }}</div>
      <div v-if="entry.attachments?.length" class="attachments">
        <span v-for="(att, i) in entry.attachments" :key="i" class="attachment-chip">
          {{ att.name ?? 'attachment' }}
        </span>
      </div>
    </div>

    <div v-else-if="isTool || isReasoning" class="tool-wrapper">
      <ToolCallBlock :title="entry.title ?? (isTool ? 'Tool call' : 'Reasoning')" :text="entry.text" />
    </div>

    <div v-else-if="isSystem" class="system-message">
      <Icon icon="mdi:information-outline" :width="14" />
      <span>{{ displayText() }}</span>
    </div>

    <div v-else class="bot-bubble">
      <div class="bubble-header">
        <div class="bot-avatar" :style="{ background: avatarColor() }">{{ avatarLabel() }}</div>
        <span class="bubble-name">{{ instance?.name ?? entry.label }}</span>
      </div>
      <div class="bubble-content">
        <div class="markdown-body">
          <template v-for="(block, i) in parsedBlocks()" :key="i">
            <div v-if="block.type === 'html'" v-html="block.content" />
            <CodeBlock v-else :language="block.language" :code="block.rawCode" />
          </template>
          <span v-if="isStreaming()" class="streaming-cursor">▍</span>
        </div>
      </div>
      <button class="copy-btn" @click="copyMarkdown">
        <Icon :icon="copied ? 'mdi:check' : 'mdi:content-copy'" :width="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.message {
  margin-bottom: 1rem;
}

.message.is-user {
  display: flex;
  justify-content: flex-end;
}

.user-bubble,
.bot-bubble {
  max-width: 70%;
  min-width: 80px;
}

.bubble-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.bubble-name {
  font-size: 0.78rem;
  font-weight: 600;
}

.user-bubble .bubble-name {
  color: var(--accent);
}

.bot-bubble .bubble-name {
  color: var(--accent);
}

.user-avatar {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  background: oklch(64% 0.18 255);
}

.user-bubble .bubble-header {
  flex-direction: row-reverse;
}

.user-bubble .bubble-content {
  background: oklch(64% 0.18 255 / 0.18);
  border-radius: 1rem 1rem 0.25rem 1rem;
  padding: 0.65rem 0.9rem;
  white-space: pre-wrap;
  font-size: 0.88rem;
}

.bot-bubble .bubble-content {
  background: oklch(23% 0.014 255);
  border-radius: 1rem 1rem 1rem 0.25rem;
  padding: 0.65rem 0.9rem;
  font-size: 0.88rem;
  position: relative;
}

.bot-bubble {
  position: relative;
}

.bot-avatar {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
}

.copy-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--muted);
  cursor: pointer;
  opacity: 0.5;
  transition: opacity 0.15s;
}

.bot-bubble:hover .copy-btn {
  opacity: 1;
}

.copy-btn:hover {
  color: var(--fg);
  background: var(--surface-2);
}

.attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.attachment-chip {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--border);
  color: var(--muted);
}

.tool-wrapper {
  padding-left: 32px;
}

.system-message {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  color: var(--muted);
  font-size: 0.82rem;
  max-width: 70%;
}

.markdown-body {
  line-height: 1.6;
}

.markdown-body :deep(p) {
  margin: 0.4rem 0;
}

.markdown-body :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.85em;
  color: var(--accent);
  background: oklch(64% 0.18 255 / 0.1);
  padding: 0.15em 0.35em;
  border-radius: 3px;
  border: 1px solid oklch(64% 0.18 255 / 0.15);
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
}

.streaming-cursor {
  animation: blink 1s step-end infinite;
  color: var(--accent);
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
