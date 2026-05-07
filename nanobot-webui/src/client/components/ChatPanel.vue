<script setup lang="ts">
import type { PublicInstance } from '../api'

defineProps<{ instances: PublicInstance[] }>()
</script>

<template>
  <section class="panel">
    <h2>Chat</h2>
    <p>Select an instance to start a websocket chat.</p>
    <select>
      <option v-for="instance in instances" :key="instance.id" :value="instance.id">
        {{ instance.name }}
      </option>
    </select>
  </section>
</template>
