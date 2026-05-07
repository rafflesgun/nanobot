export type PublicInstance = {
  id: string
  name: string
  baseUrl: string
  enabled: boolean
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
