import { readFileSync, writeFileSync } from 'node:fs'

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
  dataDir?: string
  configPath?: string
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
    dataDir: typeof env.WEBUI_DATA_DIR === 'string' && env.WEBUI_DATA_DIR.trim() ? env.WEBUI_DATA_DIR.trim() : '/data',
    configPath: typeof env.WEBUI_CONFIG === 'string' && env.WEBUI_CONFIG.trim() ? env.WEBUI_CONFIG.trim() : undefined,
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

type ConfigFileInstancePayload = {
  id: string
  name?: string
  adminBaseUrl?: string
  baseUrl?: string
  adminToken?: string
  websocketUrl?: string
  websocketToken?: string
  enabled?: boolean
}

export function writeInstancesToConfig(config: WebuiConfig, instances: ConfigFileInstancePayload[]): void {
  if (!config.configPath) throw new Error('no config file path available')
  const raw = JSON.parse(readFileSync(config.configPath, 'utf-8')) as Record<string, unknown>
  raw.instances = instances.map((inst) => {
    const existing = config.instances.find((ei) => ei.id === inst.id)
    const base = existing
      ? { id: existing.id, name: existing.name, adminBaseUrl: existing.baseUrl, adminToken: existing.adminToken, websocketUrl: existing.websocketUrl, websocketToken: existing.websocketToken, enabled: existing.enabled }
      : { id: inst.id }
    if (inst.name !== undefined) base.name = inst.name
    if (inst.adminBaseUrl !== undefined) base.adminBaseUrl = inst.adminBaseUrl
    if (inst.baseUrl !== undefined) base.adminBaseUrl = inst.baseUrl.replace(/\/$/, '')
    if (inst.adminToken !== undefined) base.adminToken = inst.adminToken
    if (inst.websocketUrl !== undefined) base.websocketUrl = inst.websocketUrl
    if (inst.websocketToken !== undefined) base.websocketToken = inst.websocketToken
    if (inst.enabled !== undefined) base.enabled = inst.enabled
    return base
  })
  writeFileSync(config.configPath, `${JSON.stringify(raw, null, 2)}\n`)
  config.instances = loadConfigFileInstances(raw as ConfigFile)
}
