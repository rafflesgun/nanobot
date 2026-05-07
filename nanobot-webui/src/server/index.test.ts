import http from 'node:http'
import { mkdtemp, rm, mkdir, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp } from './index'

let server: http.Server | undefined
let tempDirs: string[] = []

afterEach(async () => {
  await new Promise<void>((resolve, reject) => {
    if (!server) {
      resolve()
      return
    }
    server.close((error) => (error ? reject(error) : resolve()))
  })
  server = undefined
  await Promise.all(tempDirs.map((dir) => rm(dir, { recursive: true, force: true })))
  tempDirs = []
})

function listen(app: ReturnType<typeof createApp>['app']): Promise<string> {
  return new Promise((resolve) => {
    server = http.createServer(app.callback())
    server.listen(0, '127.0.0.1', () => {
      const addr = server!.address()
      if (typeof addr === 'object' && addr) resolve(`http://127.0.0.1:${addr.port}`)
    })
  })
}

describe('createApp', () => {
  it('serves built client assets without dashboard auth', async () => {
    const staticRoot = await mkdtemp(path.join(os.tmpdir(), 'nanobot-webui-static-'))
    tempDirs.push(staticRoot)
    await mkdir(path.join(staticRoot, 'assets'))
    await writeFile(path.join(staticRoot, 'index.html'), '<main>Nanobot dashboard</main>')
    await writeFile(path.join(staticRoot, 'assets', 'app.js'), 'window.loaded = true')
    const { app } = createApp(
      {
        port: 6060,
        authToken: 'dashboard',
        instances: []
      },
      { staticRoot }
    )
    const base = await listen(app)

    const index = await fetch(`${base}/`)
    const asset = await fetch(`${base}/assets/app.js`)

    expect(index.status).toBe(200)
    await expect(index.text()).resolves.toBe('<main>Nanobot dashboard</main>')
    expect(asset.status).toBe(200)
    await expect(asset.text()).resolves.toBe('window.loaded = true')
  })

  it('allows health without auth and rejects API requests without auth', async () => {
    const { app } = createApp({
      port: 6060,
      authToken: 'dashboard',
      instances: []
    })
    const base = await listen(app)

    const health = await fetch(`${base}/health`)
    const unauthorized = await fetch(`${base}/api/instances`)

    expect(health.status).toBe(200)
    await expect(health.json()).resolves.toEqual({ status: 'ok' })
    expect(unauthorized.status).toBe(401)
    await expect(unauthorized.json()).resolves.toEqual({ error: 'Unauthorized' })
  })

  it('redacts instance tokens', async () => {
    const { app } = createApp({
      port: 6060,
      authToken: 'dashboard',
      instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'secret', websocketToken: 'ws-secret', enabled: true }]
    })
    const base = await listen(app)
    const res = await fetch(`${base}/api/instances`, { headers: { authorization: 'Bearer dashboard' } })
    const payload = await res.json()

    expect(res.status).toBe(200)
    expect(payload.instances[0]).toEqual({ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true })
    expect(JSON.stringify(payload)).not.toContain('secret')
    expect(JSON.stringify(payload)).not.toContain('ws-secret')
  })

  it('proxies query string, body, and safe headers to the selected instance', async () => {
    const proxy = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 201, headers: { 'content-type': 'application/json' } }))
    const { app } = createApp(
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'secret', websocketToken: 'ws-secret', enabled: true }]
      },
      { proxyAdminRequest: proxy }
    )
    const base = await listen(app)

    const res = await fetch(`${base}/api/instances/alpha/settings?verbose=true`, {
      method: 'POST',
      headers: { authorization: 'Bearer dashboard', 'content-type': 'application/json' },
      body: JSON.stringify({ enabled: false })
    })

    expect(res.status).toBe(201)
    await expect(res.json()).resolves.toEqual({ ok: true })
    expect(proxy).toHaveBeenCalledWith({
      instance: { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'secret', websocketToken: 'ws-secret', enabled: true },
      path: '/admin/v1/settings?verbose=true',
      method: 'POST',
      headers: expect.objectContaining({ 'content-type': 'application/json' }),
      body: JSON.stringify({ enabled: false })
    })
  })

  it('preserves text and empty upstream responses without throwing', async () => {
    const proxy = vi
      .fn()
      .mockResolvedValueOnce(new Response('plain text', { status: 202, headers: { 'content-type': 'text/plain' } }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }))
    const { app } = createApp(
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'secret', websocketToken: 'ws-secret', enabled: true }]
      },
      { proxyAdminRequest: proxy }
    )
    const base = await listen(app)

    const text = await fetch(`${base}/api/instances/alpha/logs`, { headers: { authorization: 'Bearer dashboard' } })
    const empty = await fetch(`${base}/api/instances/alpha/restart`, { headers: { authorization: 'Bearer dashboard' } })

    expect(text.status).toBe(202)
    await expect(text.text()).resolves.toBe('plain text')
    expect(empty.status).toBe(204)
    await expect(empty.text()).resolves.toBe('')
  })

  it('rejects unsafe admin paths', async () => {
    const proxy = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }))
    const { app } = createApp(
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'secret', websocketToken: 'ws-secret', enabled: true }]
      },
      { proxyAdminRequest: proxy }
    )
    const base = await listen(app)

    const res = await fetch(`${base}/api/instances/alpha/..%2Fsettings`, { headers: { authorization: 'Bearer dashboard' } })

    expect(res.status).toBe(400)
    await expect(res.json()).resolves.toEqual({ error: 'invalid admin path' })
    expect(proxy).not.toHaveBeenCalled()
  })

  it('does not proxy disabled instances', async () => {
    const proxy = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200, headers: { 'content-type': 'application/json' } }))
    const { app } = createApp(
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'secret', websocketToken: 'ws-secret', enabled: false }]
      },
      { proxyAdminRequest: proxy }
    )
    const base = await listen(app)

    const res = await fetch(`${base}/api/instances/alpha/settings`, { headers: { authorization: 'Bearer dashboard' } })

    expect(res.status).toBe(403)
    await expect(res.json()).resolves.toEqual({ error: 'instance disabled' })
    expect(proxy).not.toHaveBeenCalled()
  })
})
