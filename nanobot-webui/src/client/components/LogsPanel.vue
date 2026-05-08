<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchInstanceLogs, fetchLogTail, fetchWebuiLogs, type LogInfo, type LogTail, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instance: PublicInstance | undefined }>()

const selectedLogName = ref('')
const logs = ref<LogInfo[]>([])
const tail = ref<LogTail | null>(null)
const filter = ref('')
const viewMode = ref<'formatted' | 'raw'>('formatted')
const error = ref('')
const loadingLogs = ref(false)
const loadingTail = ref(false)
const loadingWebuiLogs = ref(false)
let logsSequence = 0
let tailSequence = 0
let webuiLogsSequence = 0

const filteredLogs = computed(() => {
  const needle = filter.value.trim().toLowerCase()
  if (!needle) return logs.value
  return logs.value.filter((log) => log.name.toLowerCase().includes(needle))
})

async function loadLogs() {
  const instance = props.instance
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
  const instance = props.instance
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

async function loadWebuiLogs() {
  const sequence = ++webuiLogsSequence
  tailSequence++
  selectedLogName.value = 'webui-runtime'
  tail.value = null
  error.value = ''
  loadingWebuiLogs.value = true
  try {
    const loaded = await fetchWebuiLogs(props.token)
    if (sequence !== webuiLogsSequence) return
    tail.value = {
      name: 'WebUI Runtime',
      lines: loaded.map((entry) => [entry.at, entry.level.toUpperCase(), entry.method, entry.path, entry.status, entry.message].filter((part) => part !== undefined && part !== '').join(' '))
    }
  } catch (err) {
    if (sequence !== webuiLogsSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === webuiLogsSequence) loadingWebuiLogs.value = false
  }
}

watch(() => props.instance, loadLogs, { immediate: true })
watch(() => props.token, loadLogs)

function parseLogLine(line: string): [string, string, string] {
  const match = line.match(/^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?)\s+(\w+)\s+(.*)$/)
  if (match) return [match[1].replace(/^.*T/, '').replace(/Z$/, ''), match[2], match[3]]
  const parts = line.split(/\s+/)
  if (parts.length >= 3) return [parts[0], parts[1], parts.slice(2).join(' ')]
  return ['', '', line]
}
</script>

<template>
  <section class="panel logs-panel">
    <div class="panel-heading">
      <div>
        <h2>Logs</h2>
        <p>Inspect read-only log tails for the selected instance.</p>
      </div>
    </div>

    <p v-if="!instance" class="empty-state">No target instance selected.</p>

    <div v-else class="logs-grid">
      <div class="logs-toolbar" data-testid="logs-toolbar">
        <label>
          <span>Filter</span>
          <input v-model="filter" data-testid="logs-filter" type="search" placeholder="Filter logs">
        </label>
        <div class="view-toggle" aria-label="Log view mode">
          <button type="button" data-view="formatted" :class="{ active: viewMode === 'formatted' }" @click="viewMode = 'formatted'">Formatted</button>
          <button type="button" data-view="raw" :class="{ active: viewMode === 'raw' }" @click="viewMode = 'raw'">Raw</button>
        </div>
      </div>

      <div class="log-list" aria-label="Available logs">
        <p v-if="loadingLogs" class="empty-state">Loading logs...</p>
        <button
          class="secondary log-button"
          :class="{ 'is-selected': selectedLogName === 'webui-runtime' }"
          type="button"
          data-source="webui-runtime"
          @click="loadWebuiLogs"
        >
          WebUI Runtime
        </button>
        <p v-if="!loadingLogs && filteredLogs.length === 0" class="empty-state">No instance logs available.</p>
        <button
          v-for="log in filteredLogs"
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

      <pre v-if="tail && viewMode === 'raw'" class="log-tail" data-testid="raw-log-tail">{{ tail.lines.join('\n') }}</pre>
      <div v-else-if="tail && viewMode === 'formatted'" class="log-body" data-testid="formatted-log-tail">
        <div v-for="(line, index) in tail.lines" :key="`${tail.name}-${index}`" class="log-line" data-testid="formatted-log-line">
          <span>{{ parseLogLine(line)[0] }}</span>
          <span>{{ parseLogLine(line)[1] }}</span>
          <span>{{ parseLogLine(line)[2] }}</span>
        </div>
      </div>
      <div v-else class="log-tail empty-state">{{ loadingTail || loadingWebuiLogs ? 'Loading log tail...' : 'Select a log to view its tail.' }}</div>
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
  color: var(--muted);
  line-height: 1.5;
  margin: 0.25rem 0 0;
}

.logs-grid {
  display: grid;
  gap: 1rem;
}

.logs-toolbar label {
  display: grid;
  gap: 0.45rem;
}

.logs-toolbar {
  align-items: end;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255 / 0.88);
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  justify-content: space-between;
  padding: 1rem;
}

.logs-toolbar label {
  flex: 1 1 16rem;
}

.view-toggle {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.view-toggle button {
  border-color: var(--border);
  background: var(--surface);
}

.view-toggle button.active {
  border-color: var(--accent);
  background: oklch(64% 0.18 255 / 0.18);
  color: var(--fg);
}

.logs-toolbar span {
  color: var(--fg);
  font-weight: 700;
}

.log-list,
.log-tail {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255 / 0.88);
  padding: 1rem;
}

.log-list {
  align-items: start;
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
}

.log-button.is-selected {
  border-color: var(--accent);
  color: var(--accent);
}

.log-tail {
  margin: 0;
  min-height: 12rem;
  overflow: auto;
  white-space: pre-wrap;
}

.log-body {
  display: grid;
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin: 0;
  min-height: 12rem;
  overflow: auto;
}

.log-line {
  display: grid;
  grid-template-columns: 76px 82px minmax(0, 1fr);
  gap: 12px;
  padding: 10px 16px;
  background: oklch(17% 0.012 255);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.45;
}

.log-line span:nth-child(1),
.log-line span:nth-child(2) {
  color: var(--muted);
}

@media (max-width: 620px) {
  .log-line {
    grid-template-columns: 1fr;
    gap: 2px;
  }
}

.error-text {
  color: var(--warn);
  line-height: 1.5;
  margin: 0;
}
</style>
