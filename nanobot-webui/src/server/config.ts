export type NanobotInstance = {
  id: string
  name: string
  baseUrl: string
  adminToken: string
  websocketToken: string
  websocketUrl?: string
  enabled: boolean
}

export type WebuiConfig = {
  port: number
  authToken: string
  instances: NanobotInstance[]
}

function parsePairs(value: string | undefined, label: string): Map<string, string> {
  const map = new Map<string, string>()
  if (!value?.trim()) return map
  for (const part of value.split(',')) {
    const [rawKey, ...rest] = part.split('=')
    const key = rawKey?.trim()
    const pairValue = rest.join('=').trim()
    if (!key || !pairValue) throw new Error(`invalid ${label} entry: ${part}`)
    if (map.has(key)) throw new Error(`duplicate instance id: ${key}`)
    map.set(key, pairValue)
  }
  return map
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): WebuiConfig {
  const authToken = env.AUTH_TOKEN?.trim()
  if (!authToken) throw new Error('AUTH_TOKEN is required')

  const urls = parsePairs(env.NANOBOT_INSTANCES, 'NANOBOT_INSTANCES')
  const tokens = parsePairs(env.NANOBOT_INSTANCE_TOKENS, 'NANOBOT_INSTANCE_TOKENS')
  const websocketTokens = parsePairs(env.NANOBOT_INSTANCE_WEBSOCKET_TOKENS, 'NANOBOT_INSTANCE_WEBSOCKET_TOKENS')
  const instances: NanobotInstance[] = []

  for (const [id, baseUrl] of urls) {
    const adminToken = tokens.get(id)
    if (!adminToken) throw new Error(`missing token for instance: ${id}`)
    const websocketToken = websocketTokens.get(id)
    if (!websocketToken) throw new Error(`missing websocket token for instance: ${id}`)
    instances.push({ id, name: id, baseUrl: baseUrl.replace(/\/$/, ''), adminToken, websocketToken, enabled: true })
  }

  return {
    port: Number(env.PORT || 6060),
    authToken,
    instances
  }
}

export function publicInstance(instance: NanobotInstance) {
  return {
    id: instance.id,
    name: instance.name,
    baseUrl: instance.baseUrl,
    enabled: instance.enabled
  }
}

export function websocketUrlForInstance(instance: NanobotInstance): string {
  if (instance.websocketUrl) return instance.websocketUrl
  const url = new URL(instance.baseUrl)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.port = '8765'
  url.pathname = '/'
  url.search = ''
  url.searchParams.set('client_id', 'nanobot-webui')
  url.searchParams.set('token', instance.websocketToken)
  return url.toString()
}
