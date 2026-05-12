<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'

const props = withDefaults(defineProps<{
  title: string
  text: string
  status?: string
  icon?: string
  expandedByDefault?: boolean
}>(), {
  icon: 'mdi:lightning-bolt',
  expandedByDefault: false,
})

const expanded = ref(props.expandedByDefault)
</script>

<template>
  <div class="tool-call-block">
    <button class="tool-call-header" @click="expanded = !expanded">
      <Icon :icon="icon" class="icon-lightning" />
      <span class="title">{{ title }}</span>
      <span v-if="status" class="status-chip">{{ status }}</span>
      <Icon :icon="expanded ? 'mdi:chevron-up' : 'mdi:chevron-down'" />
    </button>
    <div v-if="expanded" class="tool-call-body">
      <pre>{{ text }}</pre>
    </div>
  </div>
</template>

<style scoped>
.tool-call-block {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  overflow: hidden;
  margin: 0.35rem 0;
}

.tool-call-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 10px;
  border: none;
  background: oklch(19% 0.014 255 / 0.5);
  color: var(--muted);
  font-size: 0.8rem;
  cursor: pointer;
  text-align: left;
}

.tool-call-header:hover {
  background: oklch(22% 0.014 255);
  color: var(--fg);
}

.icon-lightning {
  color: var(--accent);
}

.title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-chip {
  font-size: 0.68rem;
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 1px 6px;
}

.tool-call-body {
  padding: 8px 10px;
  border-top: 1px solid var(--border);
}

.tool-call-body pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--muted);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
