import { describe, expect, it, vi } from 'vitest'
import { proxyAdminRequest } from './upstream'

describe('proxyAdminRequest', () => {
  it('injects instance token and strips browser auth', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }))

    const response = await proxyAdminRequest({
      instance: { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'secret', websocketToken: 'ws-secret', enabled: true },
      path: '/admin/v1/status',
      method: 'GET',
      headers: { authorization: 'Bearer dashboard' },
      fetchImpl: fetchMock
    })

    expect(response.status).toBe(200)
    expect(await response.json()).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledWith('http://nanobot-alpha:18790/admin/v1/status', expect.objectContaining({
      method: 'GET',
      headers: { authorization: 'Bearer secret' }
    }))
  })

  it('preserves safe headers and strips sensitive browser headers', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }))

    await proxyAdminRequest({
      instance: { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'secret', websocketToken: 'ws-secret', enabled: true },
      path: '/admin/v1/status',
      method: 'POST',
      headers: {
        accept: 'application/json',
        authorization: 'Bearer dashboard',
        cookie: 'session=dashboard',
        host: 'dashboard.local',
        'content-type': 'application/json',
        'x-arbitrary': 'drop-me'
      },
      body: JSON.stringify({ ping: true }),
      fetchImpl: fetchMock
    })

    expect(fetchMock).toHaveBeenCalledWith('http://nanobot-alpha:18790/admin/v1/status', expect.objectContaining({
      method: 'POST',
      headers: {
        accept: 'application/json',
        authorization: 'Bearer secret',
        'content-type': 'application/json'
      },
      body: JSON.stringify({ ping: true })
    }))
  })
})
