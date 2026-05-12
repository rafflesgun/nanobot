<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchConversations, saveConversations, type ComposerMedia, type PublicInstance, type Conversation } from '../../api'
import { appendOutboundMessage, applyChatEvent, type TranscriptEntry, type TranscriptState } from '../../chatTranscript'
import { createChatSocket, type ChatEvent, type ChatSocket } from '../../socket'
import { useConversations } from './useConversations'
import ConversationSidebar from './ConversationSidebar.vue'
import ChatArea from './ChatArea.vue'
import NewChatDialog from './NewChatDialog.vue'
import AddMemberDialog from './AddMemberDialog.vue'

type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'error' | 'disconnected'

const props = withDefaults(defineProps<{
  token: string
  instances: PublicInstance[]
  createSocket?: (token: string) => ChatSocket
  loadConversationsApi?: typeof fetchConversations
  saveConversationsApi?: typeof saveConversations
}>(), {
  createSocket: createChatSocket,
  loadConversationsApi: () => fetchConversations,
  saveConversationsApi: () => saveConversations,
})

const socket = props.createSocket(props.token)
const sidebarCollapsed = ref(false)
const showNewChatDialog = ref(false)
const showAddMemberDialog = ref(false)
const statuses = ref<Record<string, ConnectionStatus>>({})
const isGenerating = ref(false)
const activeGeneratingIds = ref<Set<string>>(new Set())

const {
  conversations, activeConversationId, activeConversation, dateGroups,
  loadConversations, createConversation, deleteConversation, renameConversation,
  selectConversation, persistConversations,
} = useConversations({
  loadConversationsApi: props.loadConversationsApi,
  saveConversationsApi: props.saveConversationsApi,
})

const activeMembers = computed(() => {
  if (!activeConversation.value) return []
  return activeConversation.value.selectedIds
    .map((id: string) => props.instances.find((i: PublicInstance) => i.id === id))
    .filter((i: PublicInstance | undefined): i is PublicInstance => !!i?.enabled)
})

const activeEntries = computed<TranscriptEntry[]>(() => {
  return (activeConversation.value?.transcript.entries ?? []) as TranscriptEntry[]
})

const canSend = computed(() => {
  if (!activeConversation.value || activeMembers.value.length === 0) return false
  const mappings = activeConversation.value.chatMappings ?? {}
  return activeConversation.value.selectedIds.every((id: string) => {
    const m = mappings[id]
    return m && m.status === 'attached' && m.chatId
  })
})

function updateStatus(event: ChatEvent) {
  const map: Record<string, ConnectionStatus> = {
    'chat.connecting': 'connecting',
    'chat.connected': 'connected',
    'chat.connection_failed': 'error',
    'chat.disconnected': 'disconnected',
  }
  const status = map[event.event]
  if (status) {
    statuses.value[event.instanceId] = status
  }
}

function conversationForEvent(event: ChatEvent): Conversation | null {
  if (event.topicId) {
    return conversations.value.find((c: Conversation) => c.id === event.topicId) ?? null
  }
  return activeConversation.value
}

function ensureConnections(conv: Conversation) {
  if (!conv) return
  const members = conv.selectedIds
    .map(id => props.instances.find(i => i.id === id))
    .filter(i => i?.enabled)
    .map(i => i!.id)

  for (const id of members) {
    if (!statuses.value[id] || statuses.value[id] === 'idle') {
      statuses.value[id] = 'connecting'
    }
  }

  socket.emit('ensure_topic_connections', {
    topicId: conv.id,
    members,
    chatMappings: conv.chatMappings ?? {},
  })
}

function handleChatEvent(event: ChatEvent) {
  updateStatus(event)

  const conv = conversationForEvent(event)
  if (!conv) return

  if (event.event === 'attached' && event.chatId) {
    if (!conv.chatMappings) conv.chatMappings = {}
    conv.chatMappings[event.instanceId] = { chatId: event.chatId, status: 'attached' }
    persistConversations(props.token)
  }

  if (event.event === 'error' && event.topicId) {
    if (!conv.chatMappings) conv.chatMappings = {}
    const existing = conv.chatMappings[event.instanceId]
    if (existing) {
      existing.status = 'error'
      existing.lastError = event.detail ?? event.text
    } else {
      conv.chatMappings[event.instanceId] = {
        chatId: event.chatId ?? '',
        status: 'error',
        lastError: event.detail ?? event.text,
      }
    }
  }

  const instance = props.instances.find(i => i.id === event.instanceId)
  const instanceLabel = instance?.name ?? event.instanceId

  applyChatEvent(conv.transcript as import('../../chatTranscript').TranscriptState, event, instanceLabel)

  if (event.event === 'delta') {
    activeGeneratingIds.value.add(event.instanceId)
    isGenerating.value = true
  }
  if (event.event === 'stream_end' || event.event === 'turn_end') {
    activeGeneratingIds.value.delete(event.instanceId)
    if (activeGeneratingIds.value.size === 0) {
      isGenerating.value = false
    }
  }

  persistConversations(props.token)
}

function sendMessage(text: string, media: ComposerMedia[]) {
  if (!activeConversation.value) return
  socket.emit('send_group_message', {
    topicId: activeConversation.value.id,
    text,
    media: media.length > 0 ? media : undefined,
    memberIds: activeConversation.value.selectedIds,
    chatMappings: activeConversation.value.chatMappings ?? {},
  })
  appendOutboundMessage(activeConversation.value.transcript as TranscriptState, text, media)
  isGenerating.value = true
  persistConversations(props.token)
}

function stopGenerating() {
  isGenerating.value = false
  activeGeneratingIds.value.clear()
}

async function handleCreateConversation(name: string, memberIds: string[]) {
  const conv = createConversation(name, memberIds)
  ensureConnections(conv)
  await persistConversations(props.token)
  showNewChatDialog.value = false
}

function handleSelectConversation(id: string) {
  selectConversation(id)
  if (activeConversation.value) {
    ensureConnections(activeConversation.value)
  }
}

function handleDeleteConversation(id: string) {
  deleteConversation(id)
  persistConversations(props.token)
}

function handleRenameConversation(id: string, newName: string) {
  renameConversation(id, newName)
  persistConversations(props.token)
}

function addMemberToActive(instanceId: string) {
  if (!activeConversation.value) return
  if (!activeConversation.value.selectedIds.includes(instanceId)) {
    activeConversation.value.selectedIds.push(instanceId)
    ensureConnections(activeConversation.value)
    persistConversations(props.token)
  }
  showAddMemberDialog.value = false
}

function removeMemberFromActive(instanceId: string) {
  if (!activeConversation.value) return
  activeConversation.value.selectedIds = activeConversation.value.selectedIds.filter((id: string) => id !== instanceId)
  if (activeConversation.value.chatMappings) {
    delete activeConversation.value.chatMappings[instanceId]
  }
  persistConversations(props.token)
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

onMounted(() => {
  socket.on('chat_event', handleChatEvent)
  loadConversations(props.token).then(() => {
    if (activeConversation.value) {
      ensureConnections(activeConversation.value)
    }
  })
})

onUnmounted(() => {
  socket.disconnect()
})

defineExpose({
  conversations,
  activeConversationId,
  activeConversation,
  isGenerating,
  canSend,
  handleCreateConversation,
  handleDeleteConversation,
  handleRenameConversation,
  sendMessage,
  stopGenerating,
  addMemberToActive,
  removeMemberFromActive,
  toggleSidebar,
})
</script>

<template>
  <div class="chat-view">
    <ConversationSidebar
      :date-groups="dateGroups" :active-id="activeConversationId"
      :instances="instances" :collapsed="sidebarCollapsed"
      @select="handleSelectConversation" @new-chat="showNewChatDialog = true"
      @rename="handleRenameConversation" @delete="handleDeleteConversation"
      @collapse="toggleSidebar"
    />
    <div class="chat-main">
      <ChatArea
        v-if="activeConversation"
        :name="activeConversation.name" :members="activeMembers"
        :entries="activeEntries" :instances="instances"
        :connection-statuses="statuses" :is-generating="isGenerating" :can-send="canSend"
        :sidebar-collapsed="sidebarCollapsed"
        @send="sendMessage" @stop="stopGenerating"
        @add-member="showAddMemberDialog = true"
        @remove-member="removeMemberFromActive" @toggle-sidebar="toggleSidebar"
      />
      <div v-else class="no-conversation">
        <p>Select or create a conversation to start chatting</p>
      </div>
    </div>
    <NewChatDialog v-if="showNewChatDialog" :instances="instances"
      :existing-names="conversations.map((c: Conversation) => c.name)"
      @create="handleCreateConversation" @close="showNewChatDialog = false" />
    <AddMemberDialog
      v-if="showAddMemberDialog && activeConversation"
      :instances="instances" :current-member-ids="activeConversation.selectedIds"
      @add="addMemberToActive" @close="showAddMemberDialog = false"
    />
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  height: calc(100vh - 62px);
  overflow: hidden;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.no-conversation {
  flex: 1;
  display: grid;
  place-items: center;
  gap: 12px;
  color: var(--muted);
  font-size: 0.9rem;
}

@media (max-width: 768px) {
  .chat-view {
    flex-direction: column;
  }
}
</style>
