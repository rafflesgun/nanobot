import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import Koa from 'koa'
import Router from '@koa/router'
import serve from 'koa-static'
import { isDashboardAuthorized } from './auth.js'
import { registerChatBridge } from './chatBridge.js'
import type { WebuiConfig } from './config.js'
import { loadConfig, publicInstance } from './config.js'
import { proxyAdminRequest as defaultProxyAdminRequest } from './upstream.js'

type ProxyAdminRequest = typeof defaultProxyAdminRequest
type CreateAppDeps = {
  proxyAdminRequest?: ProxyAdminRequest
  staticRoot?: string
}

function findInstance(config: WebuiConfig, id: string) {
  return config.instances.find((instance) => instance.id === id)
}

function canHaveBody(method: string) {
  return method !== 'GET' && method !== 'HEAD'
}

function readRequestBody(req: Koa.ParameterizedContext['req']): Promise<string> {
  return new Promise((resolve, reject) => {
    let body = ''
    req.setEncoding('utf8')
    req.on('data', (chunk) => {
      body += chunk
    })
    req.on('end', () => resolve(body))
    req.on('error', reject)
  })
}

function isSafeAdminPath(path: string) {
  let decoded: string
  try {
    decoded = decodeURIComponent(path)
  } catch {
    return false
  }
  const segments = decoded.split('/')
  return segments.every((segment) => segment && segment !== '.' && segment !== '..')
}

async function responseBody(upstream: Response) {
  const text = await upstream.text()
  if (!text) return ''
  const contentType = upstream.headers.get('content-type') || ''
  return contentType.toLowerCase().includes('application/json') ? JSON.parse(text) : text
}

export function createApp(config: WebuiConfig, deps: CreateAppDeps = {}) {
  const app = new Koa()
  const router = new Router()
  const proxyAdminRequest = deps.proxyAdminRequest ?? defaultProxyAdminRequest

  app.use(async (ctx, next) => {
    if (ctx.path === '/health') return next()
    if (!ctx.path.startsWith('/api') && !ctx.path.startsWith('/socket.io')) return next()
    if (!isDashboardAuthorized(ctx.headers, config.authToken)) {
      ctx.status = 401
      ctx.body = { error: 'Unauthorized' }
      return
    }
    await next()
  })

  router.get('/health', (ctx) => {
    ctx.body = { status: 'ok' }
  })

  router.get('/api/instances', (ctx) => {
    ctx.body = { instances: config.instances.map(publicInstance) }
  })

  router.all(/^\/api\/instances\/([^/]+)\/(.*)$/, async (ctx) => {
    const [instanceId, kind] = ctx.captures ?? []
    const instance = findInstance(config, String(instanceId))
    if (!instance) {
      ctx.status = 404
      ctx.body = { error: 'unknown instance' }
      return
    }
    if (!instance.enabled) {
      ctx.status = 403
      ctx.body = { error: 'instance disabled' }
      return
    }
    const rest = String(kind || '')
    if (!isSafeAdminPath(rest)) {
      ctx.status = 400
      ctx.body = { error: 'invalid admin path' }
      return
    }
    const upstreamPath = `/admin/v1/${rest}${ctx.querystring ? `?${ctx.querystring}` : ''}`
    const body = canHaveBody(ctx.method) ? await readRequestBody(ctx.req) : undefined
    const upstream = await proxyAdminRequest({
      instance,
      path: upstreamPath,
      method: ctx.method,
      headers: ctx.headers as Record<string, string | string[] | undefined>,
      body
    })
    ctx.status = upstream.status
    ctx.body = await responseBody(upstream)
  })

  app.use(router.routes())
  app.use(router.allowedMethods())
  if (deps.staticRoot) app.use(serve(deps.staticRoot))

  return { app }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const config = loadConfig()
  const staticRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../client')
  const { app } = createApp(config, { staticRoot })
  const server = http.createServer(app.callback())
  registerChatBridge(server, config)
  server.listen(config.port, () => {
    console.log(`nanobot-webui listening on :${config.port}`)
  })
}
