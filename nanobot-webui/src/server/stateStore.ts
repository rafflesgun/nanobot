import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

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

export type StateInstance = {
  id: string
  name: string
  baseUrl: string
  adminToken?: string
  websocketToken?: string
  enabled: boolean
}

export type WebuiState = {
  topics: StateTopic[]
  instances: StateInstance[]
}

export type StateStore = ReturnType<typeof createStateStore>

const defaultState: WebuiState = { topics: [], instances: [] }

function statePath(dataDir: string) {
  return path.join(dataDir, 'webui-state.json')
}

function normalizeState(raw: Partial<WebuiState> | undefined): WebuiState {
  return {
    topics: Array.isArray(raw?.topics) ? raw.topics : [],
    instances: Array.isArray(raw?.instances) ? raw.instances : []
  }
}

export function publicStateInstance(instance: StateInstance) {
  return {
    id: instance.id,
    name: instance.name,
    baseUrl: instance.baseUrl,
    enabled: instance.enabled
  }
}

export function createStateStore(dataDir: string) {
  async function read(): Promise<WebuiState> {
    try {
      return normalizeState(JSON.parse(await readFile(statePath(dataDir), 'utf-8')) as Partial<WebuiState>)
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return { ...defaultState }
      throw error
    }
  }

  async function write(next: WebuiState) {
    await mkdir(dataDir, { recursive: true })
    await writeFile(statePath(dataDir), `${JSON.stringify(next, null, 2)}\n`)
  }

  return {
    read,
    async writeTopics(topics: StateTopic[]) {
      await write({ ...(await read()), topics })
    },
    async writeInstances(instances: StateInstance[]) {
      await write({ ...(await read()), instances })
    }
  }
}
