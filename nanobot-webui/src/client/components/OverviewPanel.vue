<script setup lang="ts">
import { ref, watch } from 'vue'
import { fetchInstanceStatus, type InstanceStatus, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

type StatusEntry = {
  instance: PublicInstance
  status?: InstanceStatus
  error?: string
}

const entries = ref<StatusEntry[]>([])
let loadSequence = 0

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

watch([() => props.token, () => props.instances], loadStatuses, { deep: true, immediate: true })
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
.panel-heading p { color: #69778c; margin: 0.25rem 0 0; }
.compact { min-height: 2.2rem; padding: 0 0.8rem; }
.status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.85rem; }
.status-card { border: 1px solid #dce4ef; border-radius: 0.85rem; background: #fbfdff; padding: 1rem; }
.status-card.is-degraded { border-color: #fed7aa; background: #fff7ed; }
.status-title { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.status-title span { border-radius: 999px; background: #dcfce7; color: #166534; font-size: 0.75rem; font-weight: 800; padding: 0.2rem 0.55rem; text-transform: uppercase; }
.is-degraded .status-title span { background: #ffedd5; color: #9a3412; }
dl { display: grid; gap: 0.5rem; margin: 1rem 0 0; }
dl div { display: flex; justify-content: space-between; gap: 1rem; }
dt { color: #69778c; }
dd { margin: 0; text-align: right; }
.error-text { color: #9a3412; line-height: 1.5; }
</style>
