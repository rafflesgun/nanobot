<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchStateTopics, saveStateTopics, type ChatMapping, type ComposerMedia, type PublicInstance, type StateTopic } from '../api'
import { appendOutboundMessage, applyChatEvent, createTranscriptState, type TranscriptEntry, type TranscriptState } from '../chatTranscript'
import { parseMarkdownTranscript, type InlineToken, type MarkdownBlock } from '../markdownTranscript'
import { createChatSocket, type ChatEvent, type ChatSocket } from '../socket'

type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'error' | 'disconnected'

type Topic = {
  id: string
  name: string
  selectedIds: string[]
  chatMappings: Record<string, ChatMapping>
  transcript: TranscriptState
}

const props = withDefaults(defineProps<{
  token: string
  instances: PublicInstance[]
  createSocket?: (token: string) => ChatSocket
  loadTopics?: typeof fetchStateTopics
  saveTopics?: typeof saveStateTopics
}>(), {
  createSocket: createChatSocket,
  loadTopics: () => fetchStateTopics,
  saveTopics: () => saveStateTopics
})

const message = ref('')
const pendingAttachments = ref<ComposerMedia[]>([])
const copyState = ref<Record<number, 'idle' | 'copied' | 'failed'>>({})
const statuses = ref<Record<string, ConnectionStatus>>({})
const newTopicName = ref('')
const topics = ref<Topic[]>([{ id: 'default', name: 'General', selectedIds: [], chatMappings: {}, transcript: createTranscriptState() }])
const selectedTopicId = ref('default')
const socket = props.createSocket(props.token)

const selectedTopic = computed(() => topics.value.find((topic) => topic.id === selectedTopicId.value) ?? topics.value[0])
const activeMemberIds = computed(() => selectedTopic.value.selectedIds.filter((id) => instanceFor(id)?.enabled))
const availableInstances = computed(() => props.instances.filter((instance) => !selectedTopic.value.selectedIds.includes(instance.id)))
const transcript = computed(() => selectedTopic.value.transcript.entries)
const debugEvents = computed(() => selectedTopic.value.transcript.debugEvents)

function instanceFor(instanceId: string) {
  return props.instances.find((instance) => instance.id === instanceId)
}

function instanceLabel(instanceId: string) {
  return instanceFor(instanceId)?.name ?? instanceId
}

function statusFor(instanceId: string): ConnectionStatus {
  return statuses.value[instanceId] ?? 'idle'
}

function memberStatus(instanceId: string) {
  return instanceFor(instanceId)?.enabled ? statusFor(instanceId) : 'disabled'
}

function updateStatus(event: ChatEvent) {
  if (event.event === 'chat.connecting') statuses.value[event.instanceId] = 'connecting'
  else if (event.event === 'chat.connected') statuses.value[event.instanceId] = 'connected'
  else if (event.event === 'chat.connection_failed') statuses.value[event.instanceId] = 'error'
  else if (event.event === 'chat.disconnected') statuses.value[event.instanceId] = 'disconnected'
}

function topicForEvent(event: ChatEvent) {
  if (event.topicId) return topics.value.find((topic) => topic.id === event.topicId) ?? selectedTopic.value
  return selectedTopic.value
}

function ensureTopicConnections(topic: Topic) {
  const members = topic.selectedIds.filter((id) => instanceFor(id)?.enabled)
  if (members.length === 0) return
  for (const instanceId of members) {
    if (statusFor(instanceId) === 'idle') statuses.value[instanceId] = 'connecting'
  }
  socket.emit('ensure_topic_connections', { topicId: topic.id, members, chatMappings: topic.chatMappings })
}

function addMember(instanceId: string) {
  if (selectedTopic.value.selectedIds.includes(instanceId)) return
  selectedTopic.value.selectedIds.push(instanceId)
  persistTopics()
  ensureTopicConnections(selectedTopic.value)
}

function removeMember(instanceId: string) {
  selectedTopic.value.selectedIds = selectedTopic.value.selectedIds.filter((id) => id !== instanceId)
  delete selectedTopic.value.chatMappings[instanceId]
  persistTopics()
}

function sendMessage() {
  const text = message.value.trim()
  if (!text || activeMemberIds.value.length === 0) return

  const media = [...pendingAttachments.value]
  socket.emit('send_group_message', {
    topicId: selectedTopic.value.id,
    text,
    ...(media.length > 0 ? { media } : {}),
    memberIds: [...activeMemberIds.value],
    chatMappings: selectedTopic.value.chatMappings
  })
  appendOutboundMessage(selectedTopic.value.transcript, text, media)
  persistTopics()
  message.value = ''
  pendingAttachments.value = []
}

function handleChatEvent(event: ChatEvent) {
  updateStatus(event)
  const topic = topicForEvent(event)
  if (event.event === 'attached' && event.chatId) {
    topic.chatMappings[event.instanceId] = { chatId: event.chatId, status: 'attached' }
    persistTopics()
    return
  }
  if (event.event === 'error' && event.topicId) {
    topic.chatMappings[event.instanceId] = { chatId: event.chatId, status: 'error', lastError: event.detail }
  }
  applyChatEvent(topic.transcript, event, instanceLabel(event.instanceId))
  persistTopics()
}

function createTopic() {
  const name = newTopicName.value.trim()
  if (!name) return
  const id = `${Date.now()}-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  topics.value.push({ id, name, selectedIds: [], chatMappings: {}, transcript: createTranscriptState() })
  newTopicName.value = ''
  switchTopic(id)
  persistTopics()
}

function switchTopic(topicId: string) {
  selectedTopicId.value = topicId
  pendingAttachments.value = []
  ensureTopicConnections(selectedTopic.value)
}

type PersistedTopicInput = Partial<Omit<Topic, 'transcript'>> & { transcript?: Partial<TranscriptState> }

function normalizeTopic(topic: PersistedTopicInput): Topic {
  const entries = Array.isArray(topic.transcript?.entries) ? topic.transcript.entries : []
  const debugEvents = Array.isArray(topic.transcript?.debugEvents) ? topic.transcript.debugEvents : []
  const maxEntryId = entries.reduce((max, entry) => Math.max(max, Number.isFinite(entry.id) ? entry.id : 0), 0)
  const storedNextEntryId = topic.transcript?.nextEntryId
  const nextEntryId = typeof storedNextEntryId === 'number' && Number.isFinite(storedNextEntryId) ? storedNextEntryId : maxEntryId + 1
  return {
    id: typeof topic.id === 'string' ? topic.id : 'default',
    name: typeof topic.name === 'string' ? topic.name : 'General',
    selectedIds: Array.isArray(topic.selectedIds) ? topic.selectedIds : [],
    chatMappings: topic.chatMappings && typeof topic.chatMappings === 'object' ? topic.chatMappings : {},
    transcript: { entries: entries as TranscriptEntry[], debugEvents: debugEvents as ChatEvent[], nextEntryId }
  }
}

function persistTopics() {
  void props.saveTopics(props.token, topics.value).catch(() => {})
}

function readFileAsDataUrl(file: File) {
  return new Promise<ComposerMedia>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve({ name: file.name, data_url: String(reader.result) })
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

async function addAttachments(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  const media = await Promise.all(files.map(readFileAsDataUrl))
  pendingAttachments.value.push(...media)
  input.value = ''
}

function removePendingAttachment(index: number) {
  pendingAttachments.value.splice(index, 1)
}

function markdownForEntry(entry: TranscriptEntry) {
  if (entry.kind === 'tool' || entry.kind === 'reasoning') return `### ${entry.title ?? entry.label}\n\n${entry.text}`
  return entry.text
}

async function copyMarkdown(entry: TranscriptEntry) {
  try {
    await navigator.clipboard.writeText(markdownForEntry(entry))
    copyState.value[entry.id] = 'copied'
  } catch {
    copyState.value[entry.id] = 'failed'
  }
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
  void props.loadTopics(props.token)
    .then((storedTopics) => {
      if (storedTopics.length === 0) return
      topics.value = (storedTopics as StateTopic[]).map((topic) => normalizeTopic(topic as PersistedTopicInput))
      selectedTopicId.value = topics.value[0].id
      ensureTopicConnections(topics.value[0])
    })
    .catch(() => {})
})

onUnmounted(() => {
  socket.disconnect()
})
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <h2>Chat Topics</h2>
        <p>Rooms connect their member bots automatically and keep local transcript history.</p>
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
          <span>{{ topic.name }}</span>
          <small>{{ topic.transcript.entries.length }} messages · {{ topic.selectedIds.length }} bots</small>
        </button>
      </aside>

      <main class="chat-workspace">
        <header class="chat-header">
          <div>
            <h3>{{ selectedTopic.name }}</h3>
            <p>{{ transcript.length }} saved messages</p>
          </div>
        </header>

        <div class="member-bar" data-testid="member-bar">
          <span
            v-for="memberId in selectedTopic.selectedIds"
            :key="memberId"
            class="member-chip"
            :class="`is-${memberStatus(memberId)}`"
          >
            {{ instanceLabel(memberId) }}
            <em>{{ memberStatus(memberId) }}</em>
            <button type="button" :aria-label="`Remove ${instanceLabel(memberId)}`" @click="removeMember(memberId)">×</button>
          </span>
          <div class="add-member-menu">
            <button
              v-for="instance in availableInstances"
              :key="instance.id"
              type="button"
              :data-testid="`add-member-${instance.id}`"
              @click="addMember(instance.id)"
            >
              + {{ instance.name }}
            </button>
          </div>
        </div>

        <div class="transcript" aria-live="polite">
          <div v-if="transcript.length === 0" class="empty-state">Start the topic by adding a bot and sending a message.</div>
          <article
            v-for="entry in transcript"
            :key="entry.id"
            class="transcript-entry"
            :class="[`is-${entry.kind ?? 'message'}`, `is-${entry.role}`]"
          >
            <header>
              <strong>{{ entry.title ?? entry.label }}</strong>
              <span>{{ entry.role }}</span>
              <button v-if="entry.role !== 'user'" data-testid="copy-markdown" type="button" @click="copyMarkdown(entry)">
                {{ copyState[entry.id] === 'copied' ? 'Copied' : 'Copy Markdown' }}
              </button>
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
            <div v-if="entry.attachments?.length" class="attachment-row">
              <span v-for="attachment in entry.attachments" :key="attachment.data_url" data-testid="sent-attachment" class="attachment-chip">{{ attachment.name ?? 'attachment' }}</span>
            </div>
          </article>
          <details class="debug-events">
            <summary>Debug events ({{ debugEvents.length }})</summary>
            <pre>{{ JSON.stringify(debugEvents, null, 2) }}</pre>
          </details>
        </div>

        <form class="composer" @submit.prevent="sendMessage">
          <div v-if="pendingAttachments.length" class="attachment-row">
            <button v-for="(attachment, index) in pendingAttachments" :key="attachment.data_url" type="button" class="attachment-chip" @click="removePendingAttachment(index)">
              {{ attachment.name ?? 'attachment' }} ×
            </button>
          </div>
          <textarea v-model="message" placeholder="Message this topic's bot members"></textarea>
          <div class="composer-actions">
            <label class="attachment-button">
              + File
              <input data-testid="attachment-input" type="file" multiple @change="addAttachments">
            </label>
            <button type="submit" :disabled="activeMemberIds.length === 0 || !message.trim()">Send to topic</button>
          </div>
        </form>
      </main>
    </div>
  </section>
</template>

<style scoped>
.panel-heading {
  margin-bottom: 1rem;
}

.panel-heading p,
.chat-header p,
.topic-button small {
  color: #69778c;
  line-height: 1.5;
  margin: 0.25rem 0 0;
}

.chat-shell {
  display: grid;
  grid-template-columns: minmax(13rem, 0.35fr) minmax(0, 1fr);
  gap: 1rem;
  min-height: 34rem;
}

.topic-sidebar,
.chat-workspace {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 1.1rem;
  background: rgba(8, 13, 28, 0.72);
}

.topic-sidebar {
  align-content: start;
  display: grid;
  gap: 0.75rem;
  padding: 1rem;
}

.chat-workspace {
  display: grid;
  grid-template-rows: auto auto minmax(18rem, 1fr) auto;
  overflow: hidden;
}

.topic-create {
  display: grid;
  gap: 0.5rem;
}

.topic-button {
  background: transparent;
  border-color: rgba(148, 163, 184, 0.18);
  color: #cbd5e1;
  display: grid;
  gap: 0.2rem;
  justify-self: stretch;
  text-align: left;
}

.topic-button.active {
  background: rgba(37, 99, 235, 0.2);
  border-color: rgba(96, 165, 250, 0.42);
  color: #dbeafe;
}

.chat-header,
.member-bar,
.composer {
  padding: 1rem;
}

.chat-header {
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.chat-header h3,
.chat-header p {
  margin: 0;
}

.member-bar {
  align-items: center;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.member-chip,
.attachment-chip {
  align-items: center;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.72);
  color: #dbeafe;
  display: inline-flex;
  gap: 0.4rem;
  padding: 0.35rem 0.65rem;
}

.member-chip.is-connected,
.member-chip.is-attached {
  border-color: rgba(134, 239, 172, 0.6);
}

.member-chip.is-connecting {
  border-color: rgba(147, 197, 253, 0.7);
}

.member-chip.is-error,
.member-chip.is-disconnected,
.member-chip.is-disabled {
  border-color: rgba(254, 202, 202, 0.7);
}

.member-chip em {
  color: #94a3b8;
  font-size: 0.75rem;
  font-style: normal;
}

.member-chip button {
  padding: 0 0.25rem;
}

.add-member-menu {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.transcript {
  display: grid;
  gap: 1.15rem;
  min-height: 12rem;
  overflow: auto;
  padding: 1.25rem clamp(1rem, 4vw, 3rem);
}

.transcript-entry {
  max-width: min(48rem, 100%);
}

.transcript-entry.is-user {
  justify-self: end;
}

.transcript-entry.is-user .markdown-body {
  border-radius: 1rem 1rem 0.25rem 1rem;
  background: rgba(37, 99, 235, 0.22);
  padding: 0.75rem 0.9rem;
}

.transcript-entry header {
  align-items: center;
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.transcript-entry header span {
  color: #69778c;
  font-size: 0.85rem;
}

.transcript-entry.is-tool,
.transcript-entry.is-reasoning {
  border-left: 2px solid rgba(167, 139, 250, 0.5);
  padding-left: 0.85rem;
}

.markdown-body {
  color: #d7e2f1;
  line-height: 1.55;
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

.composer {
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  display: grid;
  gap: 0.75rem;
}

.composer-actions,
.attachment-row {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.attachment-button input {
  display: none;
}

textarea {
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 1rem;
  background: rgba(15, 23, 42, 0.82);
  color: #e2e8f0;
  font: inherit;
  min-height: 6rem;
  padding: 0.85rem;
  resize: vertical;
}

button,
.attachment-button {
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
