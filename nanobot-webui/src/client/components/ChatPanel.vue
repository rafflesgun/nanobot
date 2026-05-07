<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import type { PublicInstance } from '../api'
import { createChatSocket, type ChatEvent, type ChatSocket } from '../socket'

type TranscriptEntry = {
  id: number
  instanceId: string
  label: string
  event: string
  text: string
}

type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'error' | 'disconnected'

const props = withDefaults(defineProps<{
  token: string
  instances: PublicInstance[]
  createSocket?: (token: string) => ChatSocket
}>(), {
  createSocket: createChatSocket
})

const selectedIds = ref<string[]>([])
const message = ref('')
const transcript = ref<TranscriptEntry[]>([])
const statuses = ref<Record<string, ConnectionStatus>>({})
const socket = props.createSocket(props.token)
let nextEntryId = 1

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))

function instanceLabel(instanceId: string) {
  return props.instances.find((instance) => instance.id === instanceId)?.name ?? instanceId
}

function appendEntry(entry: Omit<TranscriptEntry, 'id'>) {
  transcript.value.push({ id: nextEntryId++, ...entry })
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
  for (const instanceId of selectedIds.value) statuses.value[instanceId] = 'connecting'
  socket.emit('connect_group', { instanceIds: [...selectedIds.value] })
}

function sendMessage() {
  const text = message.value.trim()
  if (!text) return

  socket.emit('send_group_message', { text })
  appendEntry({ instanceId: 'local', label: 'You', event: 'outbound', text })
  message.value = ''
}

function handleChatEvent(event: ChatEvent) {
  updateStatus(event)
  appendEntry({
    instanceId: event.instanceId,
    label: instanceLabel(event.instanceId),
    event: event.event,
    text: event.text ?? event.detail ?? ''
  })
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

    <div class="chat-grid">
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
        <article v-for="entry in transcript" :key="entry.id" class="transcript-entry">
          <header>
            <strong>{{ entry.label }}</strong>
            <span>{{ entry.event }}</span>
          </header>
          <p>{{ entry.text }}</p>
        </article>
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

.chat-grid {
  display: grid;
  gap: 1rem;
}

.instance-picker,
.transcript,
.composer {
  border: 1px solid #dce4ef;
  border-radius: 0.85rem;
  background: #fbfdff;
  padding: 1rem;
}

.instance-picker {
  display: grid;
  gap: 0.75rem;
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
  border: 1px solid #c9d5e4;
  border-radius: 999px;
  color: #526175;
  font-size: 0.75rem;
  font-style: normal;
  grid-row: 1 / span 2;
  padding: 0.2rem 0.5rem;
}

.connection-status.is-connected {
  border-color: #86efac;
  color: #15803d;
}

.connection-status.is-connecting {
  border-color: #93c5fd;
  color: #1d4ed8;
}

.connection-status.is-error,
.connection-status.is-disconnected {
  border-color: #fecaca;
  color: #b91c1c;
}

.transcript {
  display: grid;
  gap: 0.75rem;
  min-height: 12rem;
}

.transcript-entry {
  border: 1px solid #dce4ef;
  border-radius: 0.75rem;
  background: #fff;
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

.transcript-entry p {
  margin: 0.5rem 0 0;
  white-space: pre-wrap;
}

.composer {
  display: grid;
  gap: 0.75rem;
}

textarea {
  border: 1px solid #c9d5e4;
  border-radius: 0.75rem;
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
</style>
