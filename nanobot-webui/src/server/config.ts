import { readFileSync } from 'node:fs'

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

type ConfigFileInstance = {
  id?: unknown
  name?: unknown
  adminBaseUrl?: unknown
  adminToken?: unknown
  websocketUrl?: unknown
  websocketToken?: unknown
  enabled?: unknown
}

type ConfigFile = {
  authToken?: unknown
  instances?: unknown
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

function requiredString(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new Error(`${label} is required`)
  return value.trim()
}

function readConfigFile(env: NodeJS.ProcessEnv): ConfigFile | undefined {
  const raw = env.WEBUI_CONFIG_JSON ?? (env.WEBUI_CONFIG ? readFileSync(env.WEBUI_CONFIG, 'utf-8') : undefined)
  if (!raw?.trim()) return undefined
  const parsed = JSON.parse(raw) as unknown
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('WEBUI_CONFIG must contain a JSON object')
  }
  return parsed as ConfigFile
}

function loadConfigFileInstances(file: ConfigFile): NanobotInstance[] {
  if (!Array.isArray(file.instances)) throw new Error('instances must be an array')
  const seen = new Set<string>()
  return file.instances.map((rawInstance) => {
    if (!rawInstance || typeof rawInstance !== 'object' || Array.isArray(rawInstance)) {
      throw new Error('instance must be an object')
    }
    const instance = rawInstance as ConfigFileInstance
    const id = requiredString(instance.id, 'instance id')
    if (seen.has(id)) throw new Error(`duplicate instance id: ${id}`)
    seen.add(id)
    const adminBaseUrl = requiredString(instance.adminBaseUrl, `adminBaseUrl is required for instance: ${id}`)
    const adminToken = requiredString(instance.adminToken, `adminToken is required for instance: ${id}`)
    const websocketUrl = requiredString(instance.websocketUrl, `websocketUrl is required for instance: ${id}`)
    const websocketToken = requiredString(instance.websocketToken, `websocketToken is required for instance: ${id}`)
    return {
      id,
      name: typeof instance.name === 'string' && instance.name.trim() ? instance.name.trim() : id,
      baseUrl: adminBaseUrl.replace(/\/$/, ''),
      adminToken,
      websocketUrl,
      websocketToken,
      enabled: typeof instance.enabled === 'boolean' ? instance.enabled : true
    }
  })
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): WebuiConfig {
  const file = readConfigFile(env)
  const fileAuthToken = typeof file?.authToken === 'string' ? file.authToken.trim() : ''
  const authToken = env.AUTH_TOKEN?.trim() || fileAuthToken
  if (!authToken) throw new Error('AUTH_TOKEN is required')

  if (file) {
    return {
      port: Number(env.PORT || 6060),
      authToken,
      instances: loadConfigFileInstances(file)
    }
  }

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
