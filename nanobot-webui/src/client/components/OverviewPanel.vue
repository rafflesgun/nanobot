<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { fetchInstanceStatus, fetchUsage, type InstanceStatus, type PublicInstance, type UsageSummary } from '../api'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

type StatusEntry = {
  instance: PublicInstance
  status?: InstanceStatus
  error?: string
}

const entries = ref<StatusEntry[]>([])
const selectedUsageInstanceId = ref('')
const usage = ref<UsageSummary>(zeroUsage())
const usageError = ref('')
let loadSequence = 0
let usageSequence = 0

const enabledInstances = computed(() => props.instances.filter((instance) => instance.enabled))
const usageTotals = computed(() => usage.value.totals ?? zeroUsage().totals)
const usageByDay = computed(() => Array.isArray(usage.value.by_day) ? usage.value.by_day : [])
const usageByModel = computed(() => Array.isArray(usage.value.by_model) ? usage.value.by_model : [])

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

function formatNumber(value: number) {
  return new Intl.NumberFormat().format(value)
}

function trendHeight(total: number) {
  const max = Math.max(...usageByDay.value.map((row) => row.total_tokens), 1)
  return `${Math.max(8, Math.round((total / max) * 100))}%`
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
    <div class="panel-heading">
      <div>
        <h2>Overview</h2>
        <p>{{ instances.length }} configured instances</p>
      </div>
      <button class="secondary compact" type="button" @click="loadStatuses">Refresh</button>
    </div>
    <article class="usage-panel">
      <div class="usage-heading">
        <div>
          <h3>Usage</h3>
          <p v-if="selectedUsageInstanceId">Token accounting for the selected instance.</p>
          <p v-else>No enabled instance selected.</p>
        </div>
        <select v-model="selectedUsageInstanceId" data-testid="usage-instance-select" :disabled="enabledInstances.length === 0">
          <option v-if="enabledInstances.length === 0" value="">No enabled instances</option>
          <option v-for="instance in enabledInstances" :key="instance.id" :value="instance.id">{{ instance.name }}</option>
        </select>
      </div>
      <div class="usage-cards">
        <div class="usage-card" data-testid="usage-card-total"><span>Total tokens</span><strong>{{ formatNumber(usageTotals.total_tokens) }}</strong></div>
        <div class="usage-card"><span>Input</span><strong>{{ formatNumber(usageTotals.input_tokens) }}</strong></div>
        <div class="usage-card"><span>Output</span><strong>{{ formatNumber(usageTotals.output_tokens) }}</strong></div>
        <div class="usage-card"><span>Cached</span><strong>{{ formatNumber(usageTotals.cached_tokens) }}</strong></div>
      </div>
      <div class="usage-trend" data-testid="usage-trend" aria-label="Usage trend">
        <span v-if="usageByDay.length === 0" class="muted">No token usage recorded.</span>
        <div v-for="row in usageByDay" :key="row.key" class="trend-bar" :title="`${row.key}: ${row.total_tokens}`">
          <i :style="{ height: trendHeight(row.total_tokens) }"></i>
          <small>{{ row.key.slice(5) }}</small>
        </div>
      </div>
      <div class="usage-breakdown" data-testid="usage-breakdown">
        <strong>Model breakdown</strong>
        <div v-if="usageByModel.length === 0" class="muted">No model usage yet.</div>
        <div v-for="row in usageByModel" :key="row.key" class="breakdown-row">
          <span>{{ row.key }}</span>
          <span>{{ formatNumber(row.total_tokens) }} tokens</span>
        </div>
      </div>
      <p v-if="usageError" class="error-text">{{ usageError }}</p>
      <p v-if="usage.warnings?.length" class="error-text">Skipped {{ usage.warnings[0].skipped_lines }} malformed usage lines.</p>
      <p class="pricing-note">{{ usage.pricing?.message || zeroUsage().pricing.message }}</p>
    </article>
    <div class="status-grid">
      <article v-for="entry in entries" :key="entry.instance.id" class="status-card" :class="{ 'is-degraded': entry.error }">
        <div class="status-title">
          <strong>{{ entry.instance.name }}</strong>
          <span>{{ entry.error ? 'degraded' : entry.status?.status || 'loading' }}</span>
        </div>
        <p v-if="entry.error" class="error-text">{{ entry.error }}</p>
        <dl v-else>
          <div><dt>Model</dt><dd>{{ entry.status?.model || 'unknown' }}</dd></div>
          <div><dt>Provider</dt><dd>{{ entry.status?.resolved_provider || entry.status?.provider || 'unknown' }}</dd></div>
          <div><dt>Channels</dt><dd>{{ entry.status?.channels?.join(', ') || 'none' }}</dd></div>
          <div><dt>Websocket</dt><dd>{{ entry.status?.websocket?.enabled ? 'enabled' : 'disabled' }}</dd></div>
          <div><dt>Uptime</dt><dd>{{ formatUptime(entry.status?.uptime_s) }}</dd></div>
        </dl>
      </article>
    </div>
  </section>
</template>

<style scoped>
.overview-panel { min-height: 24rem; }
.panel-heading { display: flex; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
.panel-heading p { color: #93a4bd; margin: 0.25rem 0 0; }
.compact { min-height: 2.2rem; padding: 0 0.8rem; }
.usage-panel { border: 1px solid rgba(59, 130, 246, 0.22); border-radius: 1rem; background: linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(17, 24, 39, 0.68)); margin-bottom: 1rem; padding: 1rem; }
.usage-heading { align-items: flex-start; display: flex; gap: 1rem; justify-content: space-between; }
.usage-heading h3 { margin: 0; }
.usage-heading p { color: #93a4bd; margin: 0.25rem 0 0; }
.usage-heading select { background: rgba(8, 13, 28, 0.88); border: 1px solid rgba(148, 163, 184, 0.28); border-radius: 0.7rem; color: #e5eefb; min-height: 2.3rem; padding: 0 0.7rem; }
.usage-cards { display: grid; gap: 0.75rem; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin: 1rem 0; }
.usage-card { border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 0.8rem; background: rgba(8, 13, 28, 0.58); padding: 0.85rem; }
.usage-card span { color: #93a4bd; display: block; font-size: 0.78rem; text-transform: uppercase; }
.usage-card strong { display: block; font-size: 1.45rem; margin-top: 0.25rem; }
.usage-trend { align-items: end; border: 1px solid rgba(148, 163, 184, 0.16); border-radius: 0.8rem; display: flex; gap: 0.45rem; height: 8rem; padding: 0.8rem; }
.trend-bar { align-items: center; display: flex; flex: 1; flex-direction: column; gap: 0.35rem; height: 100%; justify-content: end; min-width: 1.6rem; }
.trend-bar i { background: linear-gradient(180deg, #60a5fa, #7c3aed); border-radius: 999px 999px 0.25rem 0.25rem; display: block; width: 100%; }
.trend-bar small { color: #93a4bd; font-size: 0.68rem; }
.usage-breakdown { display: grid; gap: 0.45rem; margin-top: 0.9rem; }
.breakdown-row { display: flex; justify-content: space-between; gap: 1rem; }
.pricing-note, .muted { color: #93a4bd; }
.pricing-note { margin: 0.85rem 0 0; }
.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.85rem; }
.status-card { border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 0.85rem; background: rgba(8, 13, 28, 0.72); padding: 1rem; }
.status-card.is-degraded { border-color: rgba(251, 146, 60, 0.45); background: rgba(67, 20, 7, 0.38); }
.status-title { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.status-title span { border-radius: 999px; background: rgba(34, 197, 94, 0.16); color: #86efac; font-size: 0.75rem; font-weight: 800; padding: 0.2rem 0.55rem; text-transform: uppercase; }
.is-degraded .status-title span { background: rgba(251, 146, 60, 0.16); color: #fdba74; }
dl { display: grid; gap: 0.5rem; margin: 1rem 0 0; }
dl div { display: flex; justify-content: space-between; gap: 1rem; }
dt { color: #93a4bd; }
dd { margin: 0; text-align: right; }
.error-text { color: #fdba74; line-height: 1.5; }
</style>
