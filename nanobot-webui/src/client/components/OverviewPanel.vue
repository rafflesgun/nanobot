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

function dayBarWidth(value: number) {
  const max = Math.max(...usageByDay.value.map((r) => r.total_tokens), 1)
  return Math.max(2, Math.round((value / max) * 100))
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
    <section class="hero-panel" aria-labelledby="overview-title">
      <div class="hero-head">
        <div>
          <div class="eyebrow">Dashboard</div>
          <h2 id="overview-title">Nanobot Dashboard</h2>
        </div>
        <button class="icon-button-sm" type="button" @click="loadStatuses" title="Refresh">↻</button>
      </div>
      <p class="hero-copy">{{ instances.length }} configured instance{{ instances.length !== 1 ? 's' : '' }}. Review health, usage, and runtime status at a glance.</p>
      <div class="hero-metrics" aria-label="Runtime summary">
        <div class="metric"><div class="metric-value">{{ instances.length }}</div><div class="metric-label">instances</div></div>
        <div class="metric"><div class="metric-value">{{ entries.filter(e => !e.error).length }}</div><div class="metric-label">healthy</div></div>
        <div class="metric"><div class="metric-value">{{ formatNumber(usageTotals.total_tokens) }}</div><div class="metric-label">total tokens</div></div>
        <div class="metric"><div class="metric-value">{{ entries.filter(e => e.error).length }}</div><div class="metric-label">degraded</div></div>
      </div>
    </section>

    <div class="workgrid">
      <section class="card span-7">
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
        <div v-if="usageByDay.length > 0" class="usage-chart">
          <div v-for="row in usageByDay.slice(-14)" :key="row.key" class="chart-row">
            <span class="chart-label">{{ row.key.slice(5) }}</span>
            <div class="chart-track"><div class="chart-fill" :style="{ width: dayBarWidth(row.total_tokens) + '%' }"></div></div>
            <span class="chart-value">{{ formatNumber(row.total_tokens) }}</span>
          </div>
        </div>
        <p class="pricing-note">{{ usage.pricing?.message || 'Pricing is not configured; showing token usage only.' }}</p>
      </section>

      <section class="table-panel span-5">
        <div class="panel-header">
          <div><h3>Instances</h3><p class="muted" style="margin: 4px 0 0; font-size: 12px;">Status, model, and uptime.</p></div>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Name</th><th>Status</th><th>Model</th><th>Uptime</th></tr></thead>
            <tbody>
              <tr v-for="entry in entries" :key="entry.instance.id">
                <td>{{ entry.instance.name }}</td>
                <td><span class="pill" :class="{ 'pill-danger': entry.error }"><span class="dot" :class="entry.error ? 'danger' : 'success'"></span>{{ entry.error ? 'degraded' : entry.status?.status || 'loading' }}</span></td>
                <td class="mono" :title="entry.status?.model || ''">{{ entry.status?.model || '--' }}</td>
                <td class="mono">{{ formatUptime(entry.status?.uptime_s) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="log-panel span-12">
        <div class="panel-header">
          <div><h3>Live logs</h3><p class="muted" style="margin: 4px 0 0; font-size: 12px;">Recent WebUI runtime events.</p></div>
          <div class="top-actions"><button class="button" @click="emit('navigate', 'logs')">View all</button></div>
        </div>
        <div class="log-body">
          <div v-if="!webuiLogs || webuiLogs.length === 0" class="log-line"><span>--</span><span>--</span><span>No recent log entries.</span></div>
          <div v-for="(entry, i) in (webuiLogs ?? []).slice(0, 10)" :key="i" class="log-line">
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

.hero-panel {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255 / 0.88);
  min-height: 222px;
  padding: 22px;
  overflow: hidden;
  margin-block-end: 16px;
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

.icon-button-sm {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 7px;
  background: transparent;
  color: var(--muted);
  font-size: 14px;
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

.pill-danger {
  background: oklch(68% 0.17 25 / 0.16);
  color: var(--danger);
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  display: inline-block;
}

.dot.success { background: var(--success); }
.dot.danger { background: var(--danger); }

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

.usage-chart {
  display: grid;
  gap: 6px;
  margin: 0.75rem 0 0;
}

.chart-row {
  display: grid;
  grid-template-columns: 52px minmax(0, 1fr) 60px;
  align-items: center;
  gap: 8px;
  font-size: 11px;
}

.chart-label {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10px;
  text-align: right;
}

.chart-track {
  height: 18px;
  border-radius: 4px;
  background: oklch(14% 0.012 255);
  overflow: hidden;
}

.chart-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), oklch(54% 0.15 195));
  transition: width 200ms ease;
}

.chart-value {
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.pricing-note { color: var(--muted); margin: 0.5rem 0 0; font-size: 12px; }

.error-text { color: var(--warn); line-height: 1.5; }
</style>
