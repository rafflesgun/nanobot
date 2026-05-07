import type { NanobotInstance } from './config.js'

type ProxyArgs = {
  instance: NanobotInstance
  path: string
  method: string
  headers?: Record<string, string | string[] | undefined>
  body?: string
  fetchImpl?: typeof fetch
}

export async function proxyAdminRequest(args: ProxyArgs): Promise<Response> {
  const fetchImpl = args.fetchImpl ?? fetch
  const url = `${args.instance.baseUrl}${args.path}`
  const headers: Record<string, string> = {}
  for (const name of ['accept', 'content-type']) {
    const raw = args.headers?.[name]
    const value = Array.isArray(raw) ? raw[0] : raw
    if (value) headers[name] = value
  }
  headers.authorization = `Bearer ${args.instance.adminToken}`
  return fetchImpl(url, {
    method: args.method,
    headers,
    body: args.body
  })
}
