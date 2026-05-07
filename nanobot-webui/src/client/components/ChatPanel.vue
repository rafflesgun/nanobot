<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { PublicInstance } from '../api'
import { appendOutboundMessage, applyChatEvent, createTranscriptState, type TranscriptState } from '../chatTranscript'
import { parseMarkdownTranscript, type InlineToken, type MarkdownBlock } from '../markdownTranscript'
import { createChatSocket, type ChatEvent, type ChatSocket } from '../socket'

type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'error' | 'disconnected'

type Topic = {
  id: string
  name: string
  selectedIds: string[]
  transcript: TranscriptState
}

const props = withDefaults(defineProps<{
  token: string
  instances: PublicInstance[]
  createSocket?: (token: string) => ChatSocket
}>(), {
  createSocket: createChatSocket
})

const selectedIds = ref<string[]>([])
const message = ref('')
const statuses = ref<Record<string, ConnectionStatus>>({})
const newTopicName = ref('')
const topics = ref<Topic[]>([{ id: 'default', name: 'General', selectedIds: [], transcript: createTranscriptState() }])
const selectedTopicId = ref('default')
const socket = props.createSocket(props.token)

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))
const selectedTopic = computed(() => topics.value.find((topic) => topic.id === selectedTopicId.value) ?? topics.value[0])
const transcript = computed(() => selectedTopic.value.transcript.entries)
const debugEvents = computed(() => selectedTopic.value.transcript.debugEvents)

function instanceLabel(instanceId: string) {
  return props.instances.find((instance) => instance.id === instanceId)?.name ?? instanceId
}

function statusFor(instanceId: string): ConnectionStatus {
  return statuses.value[instanceId] ?? 'idle'
}

function updateStatus(event: ChatEvent) {
  if (event.event === 'chat.connecting') statuses.value[event.instanceId] = 'connecting'
  else if (event.event === 'chat.connected') statuses.value[event.instanceId] = 'connected'
  else if (event.event === 'chat.connection_failed') statuses.value[event.instanceId] = 'error'
  else if (event.event === 'chat.disconnected') statuses.value[event.instanceId] = 'disconnected'
}

function connectGroup() {
  if (selectedIds.value.length === 0) return
  selectedTopic.value.selectedIds = [...selectedIds.value]
  for (const instanceId of selectedIds.value) statuses.value[instanceId] = 'connecting'
  socket.emit('connect_group', { instanceIds: [...selectedIds.value] })
}

function sendMessage() {
  const text = message.value.trim()
  if (!text) return

  socket.emit('send_group_message', { text })
  appendOutboundMessage(selectedTopic.value.transcript, text)
  message.value = ''
}

function handleChatEvent(event: ChatEvent) {
  updateStatus(event)
  applyChatEvent(selectedTopic.value.transcript, event, instanceLabel(event.instanceId))
}

function createTopic() {
  const name = newTopicName.value.trim()
  if (!name) return
  const id = `${Date.now()}-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  topics.value.push({ id, name, selectedIds: [], transcript: createTranscriptState() })
  newTopicName.value = ''
  switchTopic(id)
}

function switchTopic(topicId: string) {
  selectedTopicId.value = topicId
  selectedIds.value = [...selectedTopic.value.selectedIds]
}

function markdownBlocks(text: string) {
  return parseMarkdownTranscript(text)
}

function blockKey(entryId: number, block: MarkdownBlock, index: number) {
  return `${entryId}-${block.type}-${index}`
}

function inlineKey(token: InlineToken, index: number) {
  return `${token.type}-${index}-${token.text}`
}

onMounted(() => {
  socket.on('chat_event', handleChatEvent)
})

onUnmounted(() => {
  socket.disconnect()
})
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <h2>Chat</h2>
        <p>Connect enabled instances and broadcast one prompt to the group.</p>
      </div>
    </div>

    <div class="chat-shell">
      <aside class="topic-sidebar">
        <div class="topic-create">
          <input data-testid="new-topic-name" v-model="newTopicName" type="text" placeholder="New topic name">
          <button data-testid="create-topic" type="button" :disabled="!newTopicName.trim()" @click="createTopic">Create</button>
        </div>
        <button
          v-for="topic in topics"
          :key="topic.id"
          type="button"
          class="topic-button"
          :class="{ active: topic.id === selectedTopicId }"
          :data-topic-id="topic.id"
          @click="switchTopic(topic.id)"
        >
          {{ topic.name }}
        </button>
      </aside>

      <div class="instance-picker">
        <p>Select enabled upstreams for this group chat.</p>
        <label v-for="instance in enabledInstances" :key="instance.id" class="instance-option">
          <input v-model="selectedIds" type="checkbox" :value="instance.id">
          <span>{{ instance.name }}</span>
          <small>{{ instance.baseUrl }}</small>
          <em class="connection-status" :class="`is-${statusFor(instance.id)}`">{{ statusFor(instance.id) }}</em>
        </label>
        <p v-if="enabledInstances.length === 0" class="empty-state">No enabled instances loaded.</p>
        <button data-testid="connect-group" type="button" :disabled="selectedIds.length === 0" @click="connectGroup">Connect selected</button>
      </div>

      <div class="transcript" aria-live="polite">
        <div v-if="transcript.length === 0" class="empty-state">Transcript events will appear here.</div>
        <article
          v-for="entry in transcript"
          :key="entry.id"
          class="transcript-entry"
          :class="[`is-${entry.kind ?? 'message'}`, `is-${entry.role}`]"
        >
          <header>
            <strong>{{ entry.title ?? entry.label }}</strong>
            <span>{{ entry.role }}</span>
          </header>
          <div class="markdown-body">
            <template v-for="(block, blockIndex) in markdownBlocks(entry.text)" :key="blockKey(entry.id, block, blockIndex)">
              <component :is="`h${block.level}`" v-if="block.type === 'heading'" class="markdown-heading">
                <template v-for="(token, tokenIndex) in block.content" :key="inlineKey(token, tokenIndex)">
                  <code v-if="token.type === 'inlineCode'">{{ token.text }}</code>
                  <span v-else>{{ token.text }}</span>
                </template>
              </component>
              <p v-else-if="block.type === 'paragraph'">
                <template v-for="(token, tokenIndex) in block.content" :key="inlineKey(token, tokenIndex)">
                  <code v-if="token.type === 'inlineCode'">{{ token.text }}</code>
                  <span v-else>{{ token.text }}</span>
                </template>
              </p>
              <ul v-else-if="block.type === 'list'">
                <li v-for="(item, itemIndex) in block.items" :key="itemIndex">
                  <template v-for="(token, tokenIndex) in item" :key="inlineKey(token, tokenIndex)">
                    <code v-if="token.type === 'inlineCode'">{{ token.text }}</code>
                    <span v-else>{{ token.text }}</span>
                  </template>
                </li>
              </ul>
              <pre v-else class="markdown-code"><code :data-language="block.language">{{ block.code }}</code></pre>
            </template>
          </div>
        </article>
        <details class="debug-events">
          <summary>Debug events ({{ debugEvents.length }})</summary>
          <pre>{{ JSON.stringify(debugEvents, null, 2) }}</pre>
        </details>
      </div>

      <form class="composer" @submit.prevent="sendMessage">
        <textarea v-model="message" placeholder="Message all selected instances"></textarea>
        <button type="submit" :disabled="selectedIds.length === 0 || !message.trim()">Send to group</button>
      </form>
    </div>
  </section>
</template>

<style scoped>
.panel-heading {
  margin-bottom: 1rem;
}

.panel-heading p,
.instance-picker p {
  color: #69778c;
  line-height: 1.5;
  margin: 0.25rem 0 0;
}

.chat-shell {
  display: grid;
  grid-template-columns: minmax(12rem, 0.45fr) minmax(16rem, 0.65fr) minmax(22rem, 1.4fr);
  gap: 1rem;
}

.topic-sidebar,
.instance-picker,
.transcript,
.composer {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.85rem;
  background: rgba(8, 13, 28, 0.72);
  padding: 1rem;
}

.topic-sidebar,
.instance-picker {
  display: grid;
  gap: 0.75rem;
  align-content: start;
}

.topic-create {
  display: grid;
  gap: 0.5rem;
}

.topic-button {
  background: transparent;
  border-color: rgba(148, 163, 184, 0.18);
  color: #cbd5e1;
  justify-self: stretch;
  text-align: left;
}

.topic-button.active {
  background: rgba(37, 99, 235, 0.2);
  border-color: rgba(96, 165, 250, 0.42);
  color: #dbeafe;
}

.instance-option {
  align-items: center;
  display: grid;
  gap: 0.35rem 0.65rem;
  grid-template-columns: auto 1fr auto;
}

.instance-option small {
  color: #69778c;
  grid-column: 2;
}

.connection-status {
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 999px;
  color: #94a3b8;
  font-size: 0.75rem;
  font-style: normal;
  grid-row: 1 / span 2;
  padding: 0.2rem 0.5rem;
}

.connection-status.is-connected {
  border-color: #86efac;
  color: #86efac;
}

.connection-status.is-connecting {
  border-color: #93c5fd;
  color: #93c5fd;
}

.connection-status.is-error,
.connection-status.is-disconnected {
  border-color: #fecaca;
  color: #fecaca;
}

.transcript {
  display: grid;
  gap: 0.75rem;
  min-height: 12rem;
}

.transcript-entry {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 0.75rem;
  background: rgba(15, 23, 42, 0.82);
  padding: 0.85rem;
}

.transcript-entry header {
  align-items: center;
  display: flex;
  gap: 0.5rem;
  justify-content: space-between;
}

.transcript-entry header span {
  color: #69778c;
  font-size: 0.85rem;
}

.markdown-body {
  color: #d7e2f1;
  line-height: 1.55;
  margin-top: 0.65rem;
}

.markdown-body p,
.markdown-body ul,
.markdown-heading,
.markdown-code {
  margin: 0.5rem 0 0;
}

.markdown-body p:first-child,
.markdown-body ul:first-child,
.markdown-heading:first-child,
.markdown-code:first-child {
  margin-top: 0;
}

.markdown-body p {
  white-space: pre-wrap;
}

.markdown-heading {
  color: #f8fafc;
  font-size: 1rem;
  line-height: 1.3;
}

.markdown-body ul {
  padding-left: 1.25rem;
}

.markdown-body code {
  border: 1px solid rgba(125, 211, 252, 0.18);
  border-radius: 0.35rem;
  background: rgba(2, 6, 23, 0.72);
  color: #bae6fd;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.9em;
  padding: 0.08rem 0.28rem;
}

.markdown-code {
  border: 1px solid rgba(96, 165, 250, 0.22);
  border-radius: 0.7rem;
  background: rgba(2, 6, 23, 0.88);
  overflow: auto;
  padding: 0.75rem;
}

.markdown-code code {
  border: 0;
  background: transparent;
  color: #dbeafe;
  display: block;
  padding: 0;
  white-space: pre;
}

.transcript-entry.is-tool {
  border-color: rgba(251, 191, 36, 0.36);
  background: rgba(69, 46, 8, 0.34);
}

.transcript-entry.is-reasoning {
  border-color: rgba(167, 139, 250, 0.36);
  background: rgba(46, 16, 101, 0.24);
}

.composer {
  display: grid;
  gap: 0.75rem;
}

textarea {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 0.75rem;
  background: rgba(15, 23, 42, 0.82);
  color: #e2e8f0;
  font: inherit;
  min-height: 6rem;
  padding: 0.75rem;
  resize: vertical;
}

button {
  justify-self: start;
}

.empty-state {
  color: #69778c;
}

.debug-events {
  border-top: 1px solid rgba(148, 163, 184, 0.16);
  color: #94a3b8;
  padding-top: 0.75rem;
}

.debug-events pre {
  overflow: auto;
  white-space: pre-wrap;
}

@media (max-width: 1100px) {
  .chat-shell {
    grid-template-columns: 1fr;
  }
}
</style>
