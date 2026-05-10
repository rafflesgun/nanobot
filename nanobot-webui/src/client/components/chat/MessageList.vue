<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import MessageBubble from './MessageBubble.vue'
import type { TranscriptEntry } from '../../chatTranscript'
import type { PublicInstance } from '../../api'

const props = defineProps<{
  entries: TranscriptEntry[]
  instances: PublicInstance[]
}>()

const scrollEl = ref<HTMLElement | null>(null)

function instanceFor(id: string): PublicInstance | undefined {
  return props.instances.find((i) => i.id === id)
}

function shouldAutoScroll(): boolean {
  const el = scrollEl.value
  if (!el) return true
  return el.scrollTop + el.clientHeight >= el.scrollHeight - 60
}

function scrollToBottom() {
  const el = scrollEl.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(
  () => [props.entries.length, props.entries[props.entries.length - 1]?.text],
  () => {
    if (shouldAutoScroll()) {
      nextTick(scrollToBottom)
    }
  }
)
</script>

<template>
  <div ref="scrollEl" class="message-list">
    <div class="message-list-inner">
      <template v-if="entries.length">
        <MessageBubble
          v-for="entry in entries"
          :key="entry.id"
          :entry="entry"
          :instance="instanceFor(entry.instanceId)"
        />
      </template>
      <div v-else class="empty-state">Send a message to start the conversation.</div>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message-list-inner {
  max-width: 768px;
  margin: 0 auto;
}

.empty-state {
  display: grid;
  place-items: center;
  min-height: 200px;
  color: var(--muted);
  font-size: 0.9rem;
}
</style>
