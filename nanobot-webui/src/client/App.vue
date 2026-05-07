<script setup lang="ts">
import { ref } from 'vue'
import { fetchInstances, type PublicInstance } from './api'
import InstanceList from './components/InstanceList.vue'
import ChatPanel from './components/ChatPanel.vue'

const token = ref('')
const instances = ref<PublicInstance[]>([])
const error = ref('')

async function load() {
  error.value = ''
  try {
    instances.value = await fetchInstances(token.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}
</script>

<template>
  <main>
    <header>
      <h1>Nanobot Web UI</h1>
      <input v-model="token" type="password" placeholder="Dashboard token" />
      <button @click="load">Connect</button>
    </header>
    <p v-if="error" class="error">{{ error }}</p>
    <div class="grid">
      <InstanceList :instances="instances" />
      <ChatPanel :instances="instances" />
    </div>
  </main>
</template>
