<script setup lang="ts">
import type { PublicInstance } from '../api'

defineProps<{ instances: PublicInstance[] }>()
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <h2>Chat</h2>
        <p>Websocket session launcher</p>
      </div>
    </div>
    <div class="chat-placeholder">
      <p>Select an instance to start a websocket chat.</p>
      <select :disabled="instances.length === 0">
        <option v-if="instances.length === 0">No instances loaded</option>
      <option v-for="instance in instances" :key="instance.id" :value="instance.id">
        {{ instance.name }}
      </option>
    </select>
    </div>
  </section>
</template>

<style scoped>
.panel-heading {
  margin-bottom: 1rem;
}

.panel-heading p,
.chat-placeholder p {
  color: #69778c;
  line-height: 1.5;
  margin: 0.25rem 0 0;
}

.chat-placeholder {
  display: grid;
  gap: 1rem;
  border: 1px solid #dce4ef;
  border-radius: 0.85rem;
  background: #fbfdff;
  padding: 1rem;
}
</style>
