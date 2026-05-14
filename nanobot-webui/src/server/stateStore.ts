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

export type WebuiState = {
  topics: StateTopic[]
}

const defaultState: WebuiState = { topics: [] }

function statePath(dataDir: string) {
  return path.join(dataDir, 'webui-state.json')
}

function normalizeState(raw: Partial<WebuiState> | undefined): WebuiState {
  return {
    topics: Array.isArray(raw?.topics) ? raw.topics : []
  }
}

export type StateStore = ReturnType<typeof createStateStore>

export function createStateStore(dataDir: string) {
  let writeLock: Promise<void> = Promise.resolve()

  async function read(): Promise<WebuiState> {
    try {
      return normalizeState(JSON.parse(await readFile(statePath(dataDir), 'utf-8')) as Partial<WebuiState>)
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return { ...defaultState }
      console.error(`stateStore: failed to parse ${statePath(dataDir)}, resetting to default:`, (error as Error).message)
      return { ...defaultState }
    }
  }

  async function write(next: WebuiState) {
    await writeLock
    let resolve: () => void
    writeLock = new Promise<void>((r) => { resolve = r })
    try {
      await mkdir(dataDir, { recursive: true })
      await writeFile(statePath(dataDir), `${JSON.stringify(next, null, 2)}\n`)
    } finally {
      resolve!()
    }
  }

  return {
    read,
    async writeTopics(topics: StateTopic[]) {
      const current = await read()
      await write({ ...current, topics })
    }
  }
}
