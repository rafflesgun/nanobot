import { afterEach, describe, expect, it, vi } from 'vitest'
import { deleteSubagent, fetchInstanceLogs, fetchInstanceSettings, fetchInstanceStatus, fetchLogTail, fetchStateInstances, fetchStateTopics, fetchSubagent, fetchSubagents, fetchUsage, fetchWebuiLogs, patchInstanceSettings, saveStateInstances, saveStateTopics, saveSubagent } from './api'

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

  it('loads webui runtime logs', async () => {
    const logs = [{ at: '2026-05-07T00:00:00.000Z', level: 'info', method: 'GET', path: '/api/instances', status: 200 }]
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue({ logs }) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchWebuiLogs('dashboard')).resolves.toEqual(logs)

    expect(fetchMock).toHaveBeenCalledWith('/api/webui/logs', { headers: { authorization: 'Bearer dashboard' } })
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

  it('loads usage through the dashboard proxy', async () => {
    const usage = {
      totals: { count: 1, input_tokens: 10, output_tokens: 5, total_tokens: 15, cached_tokens: 0 },
      by_day: [],
      by_model: [],
      by_channel: [],
      by_session: [],
      pricing: { configured: false, message: 'Pricing is not configured; showing token usage only.' }
    }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue(usage) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchUsage('alpha', 'dashboard', 14)).resolves.toEqual(usage)

    expect(fetchMock).toHaveBeenCalledWith('/api/instances/alpha/usage?days=14', { headers: { authorization: 'Bearer dashboard' } })
  })

  it('loads subagent lists and markdown through the dashboard proxy', async () => {
    const subagents = [{ name: 'ops-triage', description: 'Triage', model: 'test/model', source: 'workspace', editable: true }]
    const detail = { ...subagents[0], content: '---\nname: ops-triage\n---\n\nBody' }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ subagents }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue(detail) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchSubagents('alpha', 'dashboard')).resolves.toEqual(subagents)
    await expect(fetchSubagent('alpha', 'ops-triage', 'dashboard')).resolves.toEqual(detail)

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/instances/alpha/subagents', { headers: { authorization: 'Bearer dashboard' } })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/instances/alpha/subagents/ops-triage', { headers: { authorization: 'Bearer dashboard' } })
  })

  it('saves and deletes subagents through the dashboard proxy', async () => {
    const content = '---\nname: ops-triage\n---\n\nBody'
    const saved = { name: 'ops-triage', description: 'Triage', model: 'test/model', source: 'workspace', editable: true }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ subagent: saved }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ deleted: true }) })
    vi.stubGlobal('fetch', fetchMock)

    await expect(saveSubagent('alpha', 'ops-triage', 'dashboard', content)).resolves.toEqual(saved)
    await expect(deleteSubagent('alpha', 'ops-triage', 'dashboard')).resolves.toEqual({ deleted: true })

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/instances/alpha/subagents/ops-triage', {
      method: 'PUT',
      headers: { authorization: 'Bearer dashboard', 'content-type': 'application/json' },
      body: JSON.stringify({ content })
    })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/instances/alpha/subagents/ops-triage', {
      method: 'DELETE',
      headers: { authorization: 'Bearer dashboard' }
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
