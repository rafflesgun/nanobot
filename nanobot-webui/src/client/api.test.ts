import { afterEach, describe, expect, it, vi } from 'vitest'
import { fetchInstanceLogs, fetchInstanceSettings, fetchInstanceStatus, fetchLogTail, fetchStateInstances, fetchStateTopics, patchInstanceSettings, saveStateInstances, saveStateTopics } from './api'

describe('admin API helpers', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads instance status through the dashboard proxy', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ status: 'ok', model: 'gpt-4.1', provider: 'openai', uptime_s: 12.5, channels: ['websocket'], websocket: { enabled: true } })
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchInstanceStatus('alpha', 'dashboard')).resolves.toMatchObject({ status: 'ok', model: 'gpt-4.1' })

    expect(fetchMock).toHaveBeenCalledWith('/api/instances/alpha/status', { headers: { authorization: 'Bearer dashboard' } })
  })

  it('loads log names and tails through the dashboard proxy', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ logs: [{ name: 'nanobot.log' }] }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ name: 'nanobot.log', lines: ['one', 'two'] }) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchInstanceLogs('alpha', 'dashboard')).resolves.toEqual([{ name: 'nanobot.log' }])
    await expect(fetchLogTail('alpha', 'nanobot.log', 'dashboard')).resolves.toEqual({ name: 'nanobot.log', lines: ['one', 'two'] })

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/instances/alpha/logs', { headers: { authorization: 'Bearer dashboard' } })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/instances/alpha/logs/nanobot.log?tail=200', { headers: { authorization: 'Bearer dashboard' } })
  })

  it('loads and patches settings through the dashboard proxy', async () => {
    const settings = { agent: { model: 'gpt-4.1', provider: 'auto', resolved_provider: 'openai', has_api_key: true }, requires_restart: false }
    const updated = { agent: { model: 'gpt-4.1-mini', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: true }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue(settings) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue(updated) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchInstanceSettings('alpha', 'dashboard')).resolves.toEqual(settings)
    await expect(patchInstanceSettings('alpha', 'dashboard', { model: 'gpt-4.1-mini', provider: 'openai' })).resolves.toEqual(updated)

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/instances/alpha/settings', { headers: { authorization: 'Bearer dashboard' } })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/instances/alpha/settings', {
      method: 'PATCH',
      headers: { authorization: 'Bearer dashboard', 'content-type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4.1-mini', provider: 'openai' })
    })
  })

  it('throws clear errors for failed admin proxy calls', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: vi.fn() }))

    await expect(fetchInstanceStatus('alpha', 'dashboard')).rejects.toThrow('failed to load status for alpha: 503')
  })

  it('loads and saves dashboard topics state', async () => {
    const topics = [{ id: 'ops', name: 'Ops', selectedIds: ['alpha'], transcript: { entries: [], debugEvents: [] } }]
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ topics }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ topics }) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchStateTopics('dashboard')).resolves.toEqual(topics)
    await expect(saveStateTopics('dashboard', topics)).resolves.toEqual(topics)

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/state/topics', { headers: { authorization: 'Bearer dashboard' } })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/state/topics', {
      method: 'PUT',
      headers: { authorization: 'Bearer dashboard', 'content-type': 'application/json' },
      body: JSON.stringify({ topics })
    })
  })

  it('loads and saves dashboard instance drafts state', async () => {
    const instances = [{ id: 'beta', name: 'Beta', baseUrl: 'http://beta', adminToken: 'admin-secret', websocketToken: 'ws-secret', enabled: true }]
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ instances: [{ id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }] }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ instances: [{ id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }] }) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchStateInstances('dashboard')).resolves.toEqual([{ id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }])
    await expect(saveStateInstances('dashboard', instances)).resolves.toEqual([{ id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }])

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/state/instances', { headers: { authorization: 'Bearer dashboard' } })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/state/instances', {
      method: 'PUT',
      headers: { authorization: 'Bearer dashboard', 'content-type': 'application/json' },
      body: JSON.stringify({ instances })
    })
  })
})
