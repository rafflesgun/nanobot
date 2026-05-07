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
  if (!file) throw new Error('WEBUI_CONFIG is required')
  const authToken = requiredString(file.authToken, 'authToken')

  return {
    port: Number(env.PORT || 6060),
    authToken,
    instances: loadConfigFileInstances(file)
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
  const url = instance.websocketUrl ? new URL(instance.websocketUrl) : new URL(instance.baseUrl)
  if (!instance.websocketUrl) {
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.port = '8765'
    url.pathname = '/'
    url.search = ''
  }
  url.searchParams.set('client_id', 'nanobot-webui')
  url.searchParams.set('token', instance.websocketToken)
  return url.toString()
}
