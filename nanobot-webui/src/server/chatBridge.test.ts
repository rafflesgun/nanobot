import http from 'node:http'
import { EventEmitter } from 'node:events'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { io as connectSocket, type Socket } from 'socket.io-client'
import { normalizeNanobotEvent, registerChatBridge } from './chatBridge'

let server: http.Server | undefined
let sockets: Socket[] = []

type OnceEmitter = {
  once(event: string, listener: (payload: unknown) => void): unknown
}

afterEach(async () => {
  for (const socket of sockets) socket.close()
  sockets = []
  await new Promise<void>((resolve, reject) => {
    if (!server) {
      resolve()
      return
    }
    server.close((error) => (error ? reject(error) : resolve()))
  })
  server = undefined
})

function listen(): Promise<string> {
  return new Promise((resolve) => {
    server = http.createServer()
    server.listen(0, '127.0.0.1', () => {
      const addr = server!.address()
      if (typeof addr === 'object' && addr) resolve(`http://127.0.0.1:${addr.port}`)
    })
  })
}

function waitForEvent<T>(emitter: OnceEmitter, event: string): Promise<T> {
  return new Promise((resolve) => {
    emitter.once(event, (payload) => resolve(payload as T))
  })
}

function connectChat(base: string, token?: string): Socket {
  const socket = connectSocket(`${base}/chat`, {
    auth: token ? { token } : undefined,
    forceNew: true,
    reconnection: false,
    transports: ['websocket']
  })
  sockets.push(socket)
  return socket
}

class FakeWebSocket extends EventEmitter {
  static CONNECTING = 0 as const
  static OPEN = 1 as const
  static CLOSING = 2 as const
  static CLOSED = 3 as const
  static instances: FakeWebSocket[] = []
  readyState: number = FakeWebSocket.OPEN
  sent: string[] = []

  constructor(readonly url: string) {
    super()
    FakeWebSocket.instances.push(this)
  }

  send(payload: string) {
    this.sent.push(payload)
  }

  close() {
    this.readyState = 3
    this.emit('close')
  }
}

describe('normalizeNanobotEvent', () => {
  it('adds instance id and preserves chat id', () => {
    expect(normalizeNanobotEvent('alpha', '{"event":"delta","chat_id":"c1","text":"hi"}')).toEqual({
      instanceId: 'alpha',
      event: 'delta',
      chatId: 'c1',
      text: 'hi'
    })
  })

  it('returns error event for invalid json', () => {
    expect(normalizeNanobotEvent('alpha', 'not-json')).toEqual({
      instanceId: 'alpha',
      event: 'error',
      chatId: '',
      detail: 'invalid upstream frame'
    })
  })

  it('keeps trusted instance id when upstream frame includes instanceId', () => {
    expect(normalizeNanobotEvent('alpha', '{"event":"delta","chat_id":"c1","instanceId":"evil"}')).toEqual({
      instanceId: 'alpha',
      event: 'delta',
      chatId: 'c1'
    })
  })
})

describe('registerChatBridge', () => {
  it('rejects chat sockets without or with wrong dashboard token and allows the correct token', async () => {
    const base = await listen()
    registerChatBridge(server!, { port: 6060, authToken: 'dashboard', instances: [] })

    const missing = connectChat(base)
    const wrong = connectChat(base, 'wrong')
    const allowed = connectChat(base, 'dashboard')

    await expect(waitForEvent<Error>(missing, 'connect_error')).resolves.toMatchObject({ message: 'Unauthorized' })
    await expect(waitForEvent<Error>(wrong, 'connect_error')).resolves.toMatchObject({ message: 'Unauthorized' })
    await expect(waitForEvent<void>(allowed, 'connect')).resolves.toBeUndefined()
  })

  it('emits an error for disabled instances without constructing an upstream websocket', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'ws-secret', enabled: false }]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_instance', { instanceId: 'alpha', wsUrl: 'ws://nanobot-alpha/chat' })

    await expect(waitForEvent(socket, 'chat_event')).resolves.toEqual({ instanceId: 'alpha', event: 'error', chatId: '', detail: 'instance disabled' })
    expect(FakeWebSocket.instances).toHaveLength(0)
  })

  it('emits an error for invalid connect payloads without constructing an upstream websocket', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'ws-secret', enabled: true }]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_instance', null)

    await expect(waitForEvent(socket, 'chat_event')).resolves.toEqual({ instanceId: '', event: 'error', chatId: '', detail: 'invalid connect payload' })
    expect(FakeWebSocket.instances).toHaveLength(0)
  })

  it('derives upstream websocket url from the configured instance', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'ws-secret', enabled: true }]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_instance', { instanceId: 'alpha', wsUrl: 'ws://evil.internal:9999' })

    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    expect(FakeWebSocket.instances[0].url).toBe('ws://nanobot-alpha:8765/?client_id=nanobot-webui&token=ws-secret')
  })

  it('closes the active upstream before reporting failed switch attempts', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'alpha-ws-secret', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', adminToken: 'admin-secret', websocketToken: 'beta-ws-secret', enabled: false }
        ]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_instance', { instanceId: 'alpha', wsUrl: 'ws://nanobot-alpha/chat' })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    const alpha = FakeWebSocket.instances[0]
    socket.emit('connect_instance', { instanceId: 'beta', wsUrl: 'ws://nanobot-beta/chat' })
    await expect(waitForEvent(socket, 'chat_event')).resolves.toEqual({ instanceId: 'beta', event: 'error', chatId: '', detail: 'instance disabled' })

    socket.emit('send_message', { text: 'after failed switch' })

    expect(alpha.readyState).toBe(FakeWebSocket.CLOSED)
    expect(alpha.sent).toEqual([])
  })

  it('does not emit stale upstream events after switching instances', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'alpha-ws-secret', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', adminToken: 'admin-secret', websocketToken: 'beta-ws-secret', enabled: true }
        ]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')
    const events: unknown[] = []
    socket.on('chat_event', (event) => events.push(event))

    socket.emit('connect_instance', { instanceId: 'alpha', wsUrl: 'ws://nanobot-alpha/chat' })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    const stale = FakeWebSocket.instances[0]
    socket.emit('connect_instance', { instanceId: 'beta', wsUrl: 'ws://nanobot-beta/chat' })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2))

    stale.emit('message', Buffer.from('{"event":"delta","chat_id":"old","text":"stale"}'))
    stale.emit('close')

    await new Promise((resolve) => setTimeout(resolve, 25))
    expect(events).toEqual([])
  })

  it('connects multiple enabled upstream websockets for group chat', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'alpha-ws-secret', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', adminToken: 'admin-secret', websocketToken: 'beta-ws-secret', enabled: true }
        ]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_group', { instanceIds: ['alpha', 'beta'] })

    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2))
    expect(FakeWebSocket.instances.map((item) => item.url)).toEqual([
      'ws://nanobot-alpha:8765/?client_id=nanobot-webui&token=alpha-ws-secret',
      'ws://nanobot-beta:8765/?client_id=nanobot-webui&token=beta-ws-secret'
    ])
  })

  it('broadcasts group messages only to connected open upstreams', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'alpha-ws-secret', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', adminToken: 'admin-secret', websocketToken: 'beta-ws-secret', enabled: true }
        ]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_group', { instanceIds: ['alpha', 'beta'] })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2))
    socket.emit('send_group_message', { text: 'hello group' })

    await vi.waitFor(() => {
      expect(FakeWebSocket.instances[0].sent).toEqual([JSON.stringify({ text: 'hello group' })])
      expect(FakeWebSocket.instances[1].sent).toEqual([JSON.stringify({ text: 'hello group' })])
    })
  })

  it('labels group chat events by upstream instance', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      {
        port: 6060,
        authToken: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', adminToken: 'admin-secret', websocketToken: 'alpha-ws-secret', enabled: true }]
      },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('connect_group', { instanceIds: ['alpha'] })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].emit('message', Buffer.from('{"event":"delta","chat_id":"c1","text":"hi"}'))

    await expect(waitForEvent(socket, 'chat_event')).resolves.toEqual({ instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'hi' })
  })
})
