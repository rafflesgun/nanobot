<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchInstanceStatus, fetchUsage, fetchWebuiLogs, type InstanceStatus, type PublicInstance, type UsageSummary, type WebuiLogEntry } from '../api'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

const emit = defineEmits<{ navigate: [tab: string] }>()

type StatusEntry = {
  instance: PublicInstance
  status?: InstanceStatus
  error?: string
}

const entries = ref<StatusEntry[]>([])
const selectedUsageInstanceId = ref('')
const usage = ref<UsageSummary>(zeroUsage())
const usageError = ref('')
const webuiLogs = ref<WebuiLogEntry[]>([])
let loadSequence = 0
let usageSequence = 0

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))
const usageTotals = computed(() => usage.value.totals ?? zeroUsage().totals)
const usageByDay = computed(() => Array.isArray(usage.value.by_day) ? usage.value.by_day : [])
const usageByModel = computed(() => Array.isArray(usage.value.by_model) ? usage.value.by_model : [])

const firstHealthyEntry = computed(() => entries.value.find((e) => !e.error && e.status))

const tokenPercent = computed(() => {
  const total = usageTotals.value.total_tokens
  if (total === 0) return 0
  return Math.min(100, Math.round((total / 500000) * 100))
})

function zeroUsage(): UsageSummary {
  return {
    range: { days: 30 },
    totals: { count: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0, cached_tokens: 0 },
    by_day: [],
    by_model: [],
    by_channel: [],
    by_session: [],
    pricing: { configured: false, message: 'Pricing is not configured; showing token usage only.' }
  }
}

function formatUptime(value?: number) {
  if (typeof value !== 'number') return 'unknown uptime'
  if (value < 60) return `${Math.round(value)}s`
  return `${Math.round(value / 60)}m`
}

function formatNumber(value: number) {
  return new Intl.NumberFormat().format(value)
}

async function loadStatuses() {
  const sequence = ++loadSequence
  const loaded = await Promise.all(
    props.instances.map(async (instance): Promise<StatusEntry> => {
      if (!instance.enabled) return { instance, error: 'disabled' }
      try {
        return { instance, status: await fetchInstanceStatus(instance.id, props.token) }
      } catch (err) {
        return { instance, error: err instanceof Error ? err.message : String(err) }
      }
    })
  )
  if (sequence !== loadSequence) return
  entries.value = loaded
  await loadWebuiLogs()
}

async function loadUsage() {
  const sequence = ++usageSequence
  usageError.value = ''
  if (!selectedUsageInstanceId.value) {
    usage.value = zeroUsage()
    return
  }
  try {
    const loaded = await fetchUsage(selectedUsageInstanceId.value, props.token)
    if (sequence === usageSequence) usage.value = loaded
  } catch (err) {
    if (sequence !== usageSequence) return
    usage.value = zeroUsage()
    usageError.value = err instanceof Error ? err.message : String(err)
  }
}

async function loadWebuiLogs() {
  try {
    webuiLogs.value = await fetchWebuiLogs(props.token)
  } catch { webuiLogs.value = [] }
}

watch([() => props.token, () => props.instances], loadStatuses, { deep: true, immediate: true })

watch([() => props.instances, () => props.token], () => {
  const enabled = enabledInstances.value
  if (!enabled.some((instance) => instance.id === selectedUsageInstanceId.value)) {
    selectedUsageInstanceId.value = enabled[0]?.id || ''
  }
  void loadUsage()
}, { deep: true, immediate: true })

watch(selectedUsageInstanceId, loadUsage)
</script>

<template>
  <section class="panel overview-panel">
    <div class="hero">
      <section class="hero-panel" aria-labelledby="overview-title">
        <div class="hero-head">
          <div>
            <div class="eyebrow">Dashboard</div>
            <h2 id="overview-title">Nanobot management console</h2>
          </div>
          <button class="secondary compact" type="button" @click="loadStatuses">Refresh</button>
        </div>
        <p class="hero-copy">{{ instances.length }} configured instance{{ instances.length !== 1 ? 's' : '' }}. Review health, usage, and runtime status at a glance.</p>
        <div class="hero-metrics" aria-label="Runtime summary">
          <div class="metric"><div class="metric-value">{{ instances.length }}</div><div class="metric-label">instances</div></div>
          <div class="metric"><div class="metric-value">{{ entries.filter(e => !e.error).length }}</div><div class="metric-label">healthy</div></div>
          <div class="metric"><div class="metric-value">{{ formatNumber(usageTotals.total_tokens) }}</div><div class="metric-label">total tokens</div></div>
          <div class="metric"><div class="metric-value">{{ entries.filter(e => e.error).length }}</div><div class="metric-label">degraded</div></div>
        </div>
      </section>

      <aside v-if="firstHealthyEntry" class="hero-panel runtime-panel" aria-label="Runtime topology">
        <div class="card-head">
          <div>
            <h3>Runtime topology</h3>
            <p>Instance: {{ firstHealthyEntry.instance.name }}</p>
          </div>
          <span class="pill"><span class="dot success"></span>healthy</span>
        </div>
        <div class="runtime-map" aria-hidden="true">
          <div class="node a">api</div>
          <div class="node b">fs</div>
          <div class="node main">nb</div>
          <div class="node c">llm</div>
        </div>
        <div class="runtime-meta">
          <div class="mini-stat"><strong>{{ firstHealthyEntry.status?.model || 'unknown' }}</strong><span>model</span></div>
          <div class="mini-stat"><strong>{{ formatUptime(firstHealthyEntry.status?.uptime_s) }}</strong><span>uptime</span></div>
        </div>
      </aside>
    </div>

    <div class="workgrid">
      <section class="card span-4 connection-state-card">
        <div class="card-head">
          <div><h3>Connection state</h3><p>Management controls for the selected instance.</p></div>
          <span class="pill"><span class="dot success"></span>ready</span>
        </div>
        <div class="settings-list">
          <div class="setting-row"><span class="row-title">Admin channel</span><span class="row-sub">{{ firstHealthyEntry?.status?.status || 'unknown' }}</span></div>
          <div class="setting-row"><span class="row-title">WebSocket channel</span><span class="row-sub">{{ firstHealthyEntry?.status?.websocket?.enabled ? 'open' : 'closed' }}</span></div>
          <div class="setting-row"><span class="row-title">Provider</span><span class="row-sub">{{ firstHealthyEntry?.status?.resolved_provider || 'unknown' }}</span></div>
        </div>
      </section>

      <section class="card span-4 model-routing-card">
        <div class="card-head">
          <div><h3>Model routing</h3><p>Compact provider status.</p></div>
          <button class="button" @click="emit('navigate', 'manage')">Edit</button>
        </div>
        <div class="model-list">
          <div class="model-row" v-if="firstHealthyEntry">
            <span class="row-title">{{ firstHealthyEntry.status?.model || 'unknown' }}</span>
            <span class="pill"><span class="dot success"></span>primary</span>
          </div>
          <div class="model-row" v-for="entry in entries.filter(e => !e.error && e !== firstHealthyEntry)" :key="entry.instance.id">
            <span class="row-title">{{ entry.status?.model || entry.instance.name }}</span>
            <span class="pill">fallback</span>
          </div>
        </div>
      </section>

      <section class="card span-4 capacity-card">
        <div class="card-head">
          <div><h3>Capacity</h3><p>Glanceable usage indicators.</p></div>
          <span class="muted mono" style="font-size: 11px;">last 30d</span>
        </div>
        <div class="bars">
          <div class="bar-row"><span>Tokens</span><div class="bar-track"><div class="bar-fill" :style="{ width: tokenPercent + '%' }"></div></div><span class="mono muted">{{ tokenPercent }}%</span></div>
          <div class="bar-row"><span>Tools</span><div class="bar-track"><div class="bar-fill" style="width: 0%"></div></div><span class="mono muted">0%</span></div>
          <div class="bar-row"><span>Memory</span><div class="bar-track"><div class="bar-fill" style="width: 0%"></div></div><span class="mono muted">0%</span></div>
        </div>
      </section>

      <section class="table-panel span-7">
        <div class="panel-header">
          <div><h3>Instances</h3><p class="muted" style="margin: 4px 0 0; font-size: 12px;">Status, provider, and uptime.</p></div>
          <button class="button" @click="emit('navigate', 'instances')">Add instance</button>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Name</th><th>Status</th><th>Provider</th><th>Uptime</th></tr></thead>
            <tbody>
              <tr v-for="entry in entries" :key="entry.instance.id">
                <td>{{ entry.instance.name }}</td>
                <td><span class="pill"><span v-if="!entry.error" class="dot success"></span>{{ entry.error ? 'degraded' : entry.status?.status || 'loading' }}</span></td>
                <td class="mono">{{ entry.status?.resolved_provider || '--' }}</td>
                <td class="mono">{{ formatUptime(entry.status?.uptime_s) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="card span-5">
        <div class="card-head">
          <div><h3>Usage details</h3><p>Token accounting for the selected instance.</p></div>
          <select v-model="selectedUsageInstanceId" data-testid="usage-instance-select" :disabled="enabledInstances.length === 0" style="width: auto; min-height: 2rem; padding: 0 0.5rem; font-size: 12px;">
            <option v-for="instance in enabledInstances" :key="instance.id" :value="instance.id">{{ instance.name }}</option>
          </select>
        </div>
        <div class="usage-cards">
          <div class="usage-card"><span>Total</span><strong>{{ formatNumber(usageTotals.total_tokens) }}</strong></div>
          <div class="usage-card"><span>Input</span><strong>{{ formatNumber(usageTotals.input_tokens) }}</strong></div>
          <div class="usage-card"><span>Output</span><strong>{{ formatNumber(usageTotals.output_tokens) }}</strong></div>
          <div class="usage-card"><span>Cached</span><strong>{{ formatNumber(usageTotals.cached_tokens) }}</strong></div>
        </div>
        <p class="pricing-note">{{ usage.pricing?.message || 'Pricing is not configured; showing token usage only.' }}</p>
      </section>

      <section class="log-panel span-12">
        <div class="panel-header">
          <div><h3>Live logs</h3><p class="muted" style="margin: 4px 0 0; font-size: 12px;">Recent WebUI runtime events.</p></div>
          <div class="top-actions"><button class="button" @click="emit('navigate', 'logs')">View all</button></div>
        </div>
        <div class="log-body">
          <div v-if="webuiLogs.length === 0" class="log-line"><span>--</span><span>--</span><span>No recent log entries.</span></div>
          <div v-for="(entry, i) in webuiLogs.slice(0, 20)" :key="i" class="log-line">
            <span>{{ entry.at }}</span>
            <span>{{ entry.level?.toUpperCase() || 'INFO' }}</span>
            <span>{{ [entry.method, entry.path, entry.status, entry.message].filter(Boolean).join(' ') }}</span>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.overview-panel { min-height: 24rem; }

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
  gap: 16px;
  align-items: stretch;
  margin-block-end: 16px;
}

.hero-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255 / 0.88);
  min-height: 222px;
  padding: 22px;
  overflow: hidden;
}

.hero-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-block-end: 24px;
}

.eyebrow {
  color: var(--muted);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.hero-copy {
  max-width: 650px;
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.65;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-block-start: 22px;
}

.metric {
  min-width: 0;
  padding: 11px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-2);
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}

.metric-label {
  margin-block-start: 5px;
  color: var(--muted);
  font-size: 11px;
}

.runtime-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px;
}

.runtime-map {
  flex: 1;
  min-height: 136px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background:
    linear-gradient(var(--border) 1px, transparent 1px),
    linear-gradient(90deg, var(--border) 1px, transparent 1px),
    oklch(14% 0.012 255);
  background-size: 28px 28px;
  position: relative;
  overflow: hidden;
}

.node {
  position: absolute;
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 650;
}

.node.main {
  inset-block-start: 42px;
  inset-inline-start: 42%;
  border-color: color-mix(in oklch, var(--accent), var(--border) 35%);
  color: var(--accent);
}

.node.a { inset-block-start: 18px; inset-inline-start: 12%; }
.node.b { inset-block-start: 88px; inset-inline-start: 18%; }
.node.c { inset-block-start: 62px; inset-inline-end: 14%; }

.runtime-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.mini-stat {
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 11px;
  background: var(--surface-2);
}

.mini-stat strong {
  display: block;
  font-family: var(--font-mono);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.mini-stat span {
  display: block;
  margin-block-start: 4px;
  color: var(--muted);
  font-size: 10px;
}

.workgrid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 16px;
}

.card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255 / 0.88);
  padding: 16px;
}

.span-4 { grid-column: span 4; }
.span-5 { grid-column: span 5; }
.span-7 { grid-column: span 7; }
.span-12 { grid-column: span 12; }

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-block-end: 14px;
}

.card h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.card p {
  margin: 5px 0 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.55;
}

.settings-list, .model-list {
  display: grid;
  gap: 8px;
}

.setting-row, .model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 38px;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2);
  font-size: 12px;
}

.row-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 560;
}

.row-sub {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10px;
  white-space: nowrap;
}

.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 999px;
  background: oklch(70% 0.14 145 / 0.16);
  color: var(--success);
  font-size: 11px;
  font-weight: 650;
  text-transform: uppercase;
  white-space: nowrap;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.dot.success { background: var(--success); }

.bars {
  display: grid;
  gap: 12px;
  padding-block-start: 2px;
}

.bar-row {
  display: grid;
  grid-template-columns: 86px minmax(0, 1fr) 46px;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.bar-track {
  height: 7px;
  border-radius: 999px;
  background: oklch(14% 0.012 255);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: inherit;
  background: var(--fg);
}

.bar-fill.warn {
  background: var(--warn);
}

.table-panel, .log-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255 / 0.88);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 14px 16px;
  border-block-end: 1px solid var(--border);
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 650;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th, td {
  padding: 11px 16px;
  border-block-end: 1px solid var(--border);
  text-align: start;
  vertical-align: middle;
  white-space: nowrap;
}

th {
  color: var(--muted);
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

tr:last-child td {
  border-block-end: 0;
}

.table-scroll {
  overflow-x: auto;
}

.log-body {
  display: grid;
  gap: 1px;
  background: var(--border);
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

.usage-cards {
  display: grid;
  gap: 0.5rem;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  margin: 0.5rem 0;
}

.usage-card {
  border: 1px solid var(--border);
  border-radius: 0.8rem;
  background: var(--surface-2);
  padding: 0.65rem;
}

.usage-card span { color: var(--muted); display: block; font-size: 0.72rem; text-transform: uppercase; }
.usage-card strong { display: block; font-size: 1.1rem; margin-top: 0.15rem; }

.compact { min-height: 2.2rem; padding: 0 0.8rem; }
.pricing-note { color: var(--muted); margin: 0.5rem 0 0; font-size: 12px; }

.error-text { color: var(--warn); line-height: 1.5; }
</style>
