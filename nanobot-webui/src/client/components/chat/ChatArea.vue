<script setup lang="ts">
import ChatHeader from './ChatHeader.vue'
import MessageList from './MessageList.vue'
import ChatComposer from './ChatComposer.vue'
import type { TranscriptEntry } from '../../chatTranscript'
import type { PublicInstance, ComposerMedia } from '../../api'

const props = defineProps<{
  name: string
  members: PublicInstance[]
  entries: TranscriptEntry[]
  instances: PublicInstance[]
  connectionStatuses: Record<string, 'idle' | 'connecting' | 'connected' | 'error' | 'disconnected'>
  isGenerating: boolean
  canSend: boolean
  sidebarCollapsed: boolean
}>()

const emit = defineEmits<{
  send: [text: string, media: ComposerMedia[], mentionedIds: string[]]
  stop: []
  addMember: []
  removeMember: [instanceId: string]
  toggleSidebar: []
}>()
</script>

<template>
  <div class="chat-area">
    <ChatHeader
      :name="props.name"
      :members="props.members"
      :connection-statuses="props.connectionStatuses"
      :sidebar-collapsed="props.sidebarCollapsed"
      @add-member="emit('addMember')"
      @remove-member="emit('removeMember', $event)"
      @toggle-sidebar="emit('toggleSidebar')"
    />
    <MessageList :entries="props.entries" :instances="props.instances" />
    <ChatComposer
      :disabled="!props.canSend"
      :is-generating="props.isGenerating"
      :members="props.members"
      :connection-statuses="props.connectionStatuses"
      @send="(text: string, media: ComposerMedia[], mentionedIds: string[]) => emit('send', text, media, mentionedIds)"
      @stop="emit('stop')"
    />
  </div>
</template>

<style scoped>
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
</style>
