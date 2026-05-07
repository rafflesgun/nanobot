export type PublicInstance = {
  id: string
  name: string
  baseUrl: string
  enabled: boolean
}

export type ChatMapping = {
  chatId: string
  status: 'pending' | 'attached' | 'error'
  lastError?: string
}

export type ComposerMedia = {
  data_url: string
  name?: string
}

export type StateTopic = {
  id: string
  name: string
  selectedIds: string[]
  chatMappings?: Record<string, ChatMapping>
  transcript: {
    entries: Array<{
      id: number
      instanceId: string
      chatId: string
      role: string
      label: string
      event: string
      text: string
      kind?: string
      title?: string
      attachments?: ComposerMedia[]
    }>
    debugEvents: unknown[]
    nextEntryId?: number
  }
}

export type StateInstance = PublicInstance & {
  adminToken?: string
  websocketToken?: string
}

export type InstanceStatus = {
  status: string
  model?: string
  provider?: string
  resolved_provider?: string
  uptime_s?: number
  channels?: string[]
  websocket?: { enabled?: boolean }
}

export type LogInfo = { name: string }
export type LogTail = { name: string; lines: string[] }
export type WebuiLogEntry = {
  at: string
  level: string
  method?: string
  path?: string
  status?: number
  message?: string
}

export type InstanceSettings = {
  agent: {
    model: string
    provider: string
    resolved_provider: string
    has_api_key: boolean
  }
  requires_restart: boolean
}

export type SettingsPatch = {
  model?: string
  provider?: string
}

export type SubagentSummary = {
  name: string
  description: string
  model: string
  tools?: string[]
  max_iterations?: number
  max_tokens?: number
  source: 'builtin' | 'workspace'
  editable: boolean
}

export type SubagentDetail = SubagentSummary & { content: string }

export type UsageTotals = {
  count: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cached_tokens: number
}

export type UsageBreakdown = UsageTotals & { key: string }

export type UsageSummary = {
  range?: { days: number }
  totals: UsageTotals
  by_day: UsageBreakdown[]
  by_model: UsageBreakdown[]
  by_channel: UsageBreakdown[]
  by_session: UsageBreakdown[]
  pricing: { configured: false; message: string }
  warnings?: Array<{ skipped_lines: number }>
}

function authHeaders(token: string) {
  return { authorization: `Bearer ${token}` }
}

async function readJson<T>(res: Response, errorMessage: string): Promise<T> {
  if (!res.ok) throw new Error(`${errorMessage}: ${res.status}`)
  return (await res.json()) as T
}

export async function fetchInstances(token: string): Promise<PublicInstance[]> {
  const res = await fetch('/api/instances', { headers: authHeaders(token) })
  const payload = await readJson<{ instances: PublicInstance[] }>(res, 'failed to load instances')
  return payload.instances
}

export async function fetchInstanceStatus(instanceId: string, token: string): Promise<InstanceStatus> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/status`, { headers: authHeaders(token) })
  return readJson<InstanceStatus>(res, `failed to load status for ${instanceId}`)
}

export async function fetchInstanceLogs(instanceId: string, token: string): Promise<LogInfo[]> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/logs`, { headers: authHeaders(token) })
  const payload = await readJson<{ logs: LogInfo[] }>(res, `failed to load logs for ${instanceId}`)
  return payload.logs
}

export async function fetchLogTail(instanceId: string, name: string, token: string): Promise<LogTail> {
  const encodedName = encodeURIComponent(name)
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/logs/${encodedName}?tail=200`, { headers: authHeaders(token) })
  return readJson<LogTail>(res, `failed to load ${name} for ${instanceId}`)
}

export async function fetchWebuiLogs(token: string): Promise<WebuiLogEntry[]> {
  const res = await fetch('/api/webui/logs', { headers: authHeaders(token) })
  const payload = await readJson<{ logs: WebuiLogEntry[] }>(res, 'failed to load webui logs')
  return payload.logs
}

export async function fetchInstanceSettings(instanceId: string, token: string): Promise<InstanceSettings> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/settings`, { headers: authHeaders(token) })
  return readJson<InstanceSettings>(res, `failed to load settings for ${instanceId}`)
}

export async function patchInstanceSettings(instanceId: string, token: string, patch: SettingsPatch): Promise<InstanceSettings> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/settings`, {
    method: 'PATCH',
    headers: { ...authHeaders(token), 'content-type': 'application/json' },
    body: JSON.stringify(patch)
  })
  return readJson<InstanceSettings>(res, `failed to update settings for ${instanceId}`)
}

export async function fetchSubagents(instanceId: string, token: string): Promise<SubagentSummary[]> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/subagents`, { headers: authHeaders(token) })
  const payload = await readJson<{ subagents: SubagentSummary[] }>(res, `failed to load subagents for ${instanceId}`)
  return payload.subagents
}

export async function fetchSubagent(instanceId: string, name: string, token: string): Promise<SubagentDetail> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/subagents/${encodeURIComponent(name)}`, { headers: authHeaders(token) })
  return readJson<SubagentDetail>(res, `failed to load subagent ${name}`)
}

export async function saveSubagent(instanceId: string, name: string, token: string, content: string): Promise<SubagentSummary> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/subagents/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { ...authHeaders(token), 'content-type': 'application/json' },
    body: JSON.stringify({ content })
  })
  const payload = await readJson<{ subagent: SubagentSummary }>(res, `failed to save subagent ${name}`)
  return payload.subagent
}

export async function deleteSubagent(instanceId: string, name: string, token: string): Promise<{ deleted: boolean }> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/subagents/${encodeURIComponent(name)}`, { method: 'DELETE', headers: authHeaders(token) })
  return readJson<{ deleted: boolean }>(res, `failed to delete subagent ${name}`)
}

export async function fetchUsage(instanceId: string, token: string, days = 30): Promise<UsageSummary> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/usage?days=${encodeURIComponent(String(days))}`, { headers: authHeaders(token) })
  return readJson<UsageSummary>(res, `failed to load usage for ${instanceId}`)
}

export async function fetchStateTopics(token: string): Promise<StateTopic[]> {
  const res = await fetch('/api/state/topics', { headers: authHeaders(token) })
  const payload = await readJson<{ topics: StateTopic[] }>(res, 'failed to load topics')
  return payload.topics
}

export async function saveStateTopics(token: string, topics: StateTopic[]): Promise<StateTopic[]> {
  const res = await fetch('/api/state/topics', {
    method: 'PUT',
    headers: { ...authHeaders(token), 'content-type': 'application/json' },
    body: JSON.stringify({ topics })
  })
  const payload = await readJson<{ topics: StateTopic[] }>(res, 'failed to save topics')
  return payload.topics
}

export async function fetchStateInstances(token: string): Promise<PublicInstance[]> {
  const res = await fetch('/api/state/instances', { headers: authHeaders(token) })
  const payload = await readJson<{ instances: PublicInstance[] }>(res, 'failed to load instance drafts')
  return payload.instances
}

export async function saveStateInstances(token: string, instances: StateInstance[]): Promise<PublicInstance[]> {
  const res = await fetch('/api/state/instances', {
    method: 'PUT',
    headers: { ...authHeaders(token), 'content-type': 'application/json' },
    body: JSON.stringify({ instances })
  })
  const payload = await readJson<{ instances: PublicInstance[] }>(res, 'failed to save instance drafts')
  return payload.instances
}
