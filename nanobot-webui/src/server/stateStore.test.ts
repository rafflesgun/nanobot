import { mkdtemp, readFile, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { createStateStore, type StateTopic } from './stateStore'

let tempDirs: string[] = []

afterEach(async () => {
  await Promise.all(tempDirs.map((dir) => rm(dir, { recursive: true, force: true })))
  tempDirs = []
})

async function tempDataDir() {
  const dir = await mkdtemp(path.join(os.tmpdir(), 'nanobot-webui-state-'))
  tempDirs.push(dir)
  return dir
}

describe('stateStore', () => {
  it('returns empty defaults when the state file does not exist', async () => {
    const store = createStateStore(await tempDataDir())

    await expect(store.read()).resolves.toEqual({ topics: [] })
  })

  it('persists topics to a json file under the data directory', async () => {
    const dataDir = await tempDataDir()
    const store = createStateStore(dataDir)
    const topics: StateTopic[] = [
      {
        id: 'ops',
        name: 'Ops',
        selectedIds: ['alpha'],
        transcript: {
          entries: [{ id: 1, role: 'assistant', label: 'alpha', text: 'hello', instanceId: 'alpha', chatId: 'c1', event: 'delta' }],
          debugEvents: [{ instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'hello' }]
        }
      }
    ]

    await store.writeTopics(topics)

    await expect(store.read()).resolves.toMatchObject({ topics })
    const raw = JSON.parse(await readFile(path.join(dataDir, 'webui-state.json'), 'utf-8'))
    expect(raw.topics).toEqual(topics)
  })

  it('persists topic chat mappings and transcript attachment metadata', async () => {
    const dataDir = await tempDataDir()
    const store = createStateStore(dataDir)
    const topics: StateTopic[] = [
      {
        id: 'ops',
        name: 'Ops',
        selectedIds: ['alpha'],
        chatMappings: { alpha: { chatId: 'chat-alpha', status: 'attached' } },
        transcript: {
          entries: [
            {
              id: 1,
              role: 'user',
              label: 'You',
              text: 'see file',
              instanceId: 'local',
              chatId: '',
              event: 'outbound',
              attachments: [{ name: 'notes.txt', data_url: 'data:text/plain;base64,bm90ZXM=' }]
            }
          ],
          debugEvents: []
        }
      }
    ]

    await store.writeTopics(topics)

    await expect(store.read()).resolves.toEqual({ topics })
  })
})
