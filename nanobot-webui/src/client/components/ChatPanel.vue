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
const socket = props.createSocket(props.token)
let nextEntryId = 1

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))

function instanceLabel(instanceId: string) {
  return props.instances.find((instance) => instance.id === instanceId)?.name ?? instanceId
}

function appendEntry(entry: Omit<TranscriptEntry, 'id'>) {
  transcript.value.push({ id: nextEntryId++, ...entry })
}

function connectGroup() {
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
        </label>
        <p v-if="enabledInstances.length === 0" class="empty-state">No enabled instances loaded.</p>
        <button data-testid="connect-group" type="button" @click="connectGroup">Connect selected</button>
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
        <button type="submit">Send to group</button>
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
  grid-template-columns: auto 1fr;
}

.instance-option small {
  color: #69778c;
  grid-column: 2;
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
