<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchInstanceLogs, fetchLogTail, type LogInfo, type LogTail, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

const selectedInstanceId = ref('')
const selectedLogName = ref('')
const logs = ref<LogInfo[]>([])
const tail = ref<LogTail | null>(null)
const error = ref('')
const loadingLogs = ref(false)
const loadingTail = ref(false)
let logsSequence = 0
let tailSequence = 0

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))
const selectedInstance = computed(() => enabledInstances.value.find((instance) => instance.id === selectedInstanceId.value))

async function loadLogs() {
  const instance = selectedInstance.value
  const sequence = ++logsSequence
  tailSequence++
  selectedLogName.value = ''
  tail.value = null
  logs.value = []
  error.value = ''

  if (!instance) {
    loadingLogs.value = false
    return
  }

  loadingLogs.value = true
  try {
    const loaded = await fetchInstanceLogs(instance.id, props.token)
    if (sequence !== logsSequence) return
    logs.value = loaded
  } catch (err) {
    if (sequence !== logsSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === logsSequence) loadingLogs.value = false
  }
}

async function loadTail(name: string) {
  const instance = selectedInstance.value
  if (!instance) return

  const sequence = ++tailSequence
  selectedLogName.value = name
  tail.value = null
  error.value = ''
  loadingTail.value = true
  try {
    const loaded = await fetchLogTail(instance.id, name, props.token)
    if (sequence !== tailSequence) return
    tail.value = loaded
  } catch (err) {
    if (sequence !== tailSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === tailSequence) loadingTail.value = false
  }
}

watch(enabledInstances, (instances) => {
  if (instances.some((instance) => instance.id === selectedInstanceId.value)) return
  selectedInstanceId.value = instances[0]?.id ?? ''
}, { immediate: true })

watch([selectedInstanceId, () => props.token], loadLogs, { immediate: true })
</script>

<template>
  <section class="panel logs-panel">
    <div class="panel-heading">
      <div>
        <h2>Logs</h2>
        <p>Inspect read-only log tails for enabled instances.</p>
      </div>
    </div>

    <p v-if="enabledInstances.length === 0" class="empty-state">No enabled instances loaded.</p>

    <div v-else class="logs-grid">
      <label class="instance-select">
        <span>Instance</span>
        <select v-model="selectedInstanceId">
          <option v-for="instance in enabledInstances" :key="instance.id" :value="instance.id">
            {{ instance.name }}
          </option>
        </select>
      </label>

      <div class="log-list" aria-label="Available logs">
        <p v-if="loadingLogs" class="empty-state">Loading logs...</p>
        <p v-else-if="logs.length === 0" class="empty-state">No logs available.</p>
        <button
          v-for="log in logs"
          :key="log.name"
          class="secondary log-button"
          :class="{ 'is-selected': log.name === selectedLogName }"
          type="button"
          :data-log="log.name"
          @click="loadTail(log.name)"
        >
          {{ log.name }}
        </button>
      </div>

      <p v-if="error" class="error-text">{{ error }}</p>

      <pre v-if="tail" class="log-tail">{{ tail.lines.join('\n') }}</pre>
      <div v-else class="log-tail empty-state">{{ loadingTail ? 'Loading log tail...' : 'Select a log to view its tail.' }}</div>
    </div>
  </section>
</template>

<style scoped>
.logs-panel {
  min-height: 24rem;
}

.panel-heading {
  margin-bottom: 1rem;
}

.panel-heading p,
.empty-state {
  color: #69778c;
  line-height: 1.5;
  margin: 0.25rem 0 0;
}

.logs-grid {
  display: grid;
  gap: 1rem;
}

.instance-select {
  display: grid;
  gap: 0.45rem;
}

.instance-select span {
  color: #44546a;
  font-weight: 700;
}

.log-list,
.log-tail {
  border: 1px solid #dce4ef;
  border-radius: 0.85rem;
  background: #fbfdff;
  padding: 1rem;
}

.log-list {
  align-items: start;
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.log-button.is-selected {
  border-color: #2563eb;
  color: #1d4ed8;
}

.log-tail {
  margin: 0;
  min-height: 12rem;
  overflow: auto;
  white-space: pre-wrap;
}

.error-text {
  color: #9a3412;
  line-height: 1.5;
  margin: 0;
}
</style>
