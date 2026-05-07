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
  readyState: number = FakeWebSocket.CONNECTING
  sent: string[] = []

  constructor(readonly url: string) {
    super()
    FakeWebSocket.instances.push(this)
  }

  send(payload: string) {
    this.sent.push(payload)
  }

  open() {
    this.readyState = FakeWebSocket.OPEN
    this.emit('open')
  }

  fail() {
    this.emit('error')
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
    expect(events).not.toContainEqual({ instanceId: 'alpha', event: 'delta', chatId: 'old', text: 'stale' })
    expect(events).not.toContainEqual({ instanceId: 'alpha', event: 'chat.disconnected', chatId: '' })
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

  it('ensures topic connections by sending new_chat for members without mappings', async () => {
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

    socket.emit('ensure_topic_connections', { topicId: 'ops', members: ['alpha'], chatMappings: {} })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].open()

    await vi.waitFor(() => expect(FakeWebSocket.instances[0].sent).toEqual([JSON.stringify({ type: 'new_chat' })]))
  })

  it('ensures topic connections by attaching mapped chats', async () => {
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

    socket.emit('ensure_topic_connections', {
      topicId: 'ops',
      members: ['alpha'],
      chatMappings: { alpha: { chatId: 'chat-alpha', status: 'attached' } }
    })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].open()

    await vi.waitFor(() => expect(FakeWebSocket.instances[0].sent).toEqual([JSON.stringify({ type: 'attach', chat_id: 'chat-alpha' })]))
  })

  it('emits connection lifecycle events for upstream websockets', async () => {
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

    const events: unknown[] = []
    socket.on('chat_event', (event) => events.push(event))
    socket.emit('connect_group', { instanceIds: ['alpha'] })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].open()
    FakeWebSocket.instances[0].close()

    await vi.waitFor(() => expect(events).toContainEqual({ instanceId: 'alpha', event: 'chat.connected', chatId: '' }))
    expect(events).toContainEqual({ instanceId: 'alpha', event: 'chat.connecting', chatId: '' })
    expect(events).toContainEqual({ instanceId: 'alpha', event: 'chat.disconnected', chatId: '' })
  })

  it('emits connection failed when upstream websocket errors', async () => {
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

    const events: unknown[] = []
    socket.on('chat_event', (event) => events.push(event))
    socket.emit('connect_group', { instanceIds: ['alpha'] })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].fail()

    await vi.waitFor(() => expect(events).toContainEqual({ instanceId: 'alpha', event: 'chat.connection_failed', chatId: '' }))
  })

  it('reports not attached for topic members without chat mappings', async () => {
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

    socket.emit('connect_group', { instanceIds: ['alpha', 'beta'] })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2))
    for (const upstream of FakeWebSocket.instances) upstream.open()
    socket.emit('send_group_message', { topicId: 'ops', text: 'hello group', memberIds: ['alpha', 'beta'], chatMappings: {} })

    await vi.waitFor(() => expect(events).toContainEqual({ topicId: 'ops', instanceId: 'alpha', event: 'error', chatId: '', detail: 'not attached' }))
    expect(events).toContainEqual({ topicId: 'ops', instanceId: 'beta', event: 'error', chatId: '', detail: 'not attached' })
    expect(FakeWebSocket.instances[0].sent).toEqual([])
    expect(FakeWebSocket.instances[1].sent).toEqual([])
  })

  it('sends typed topic messages only to mapped open members', async () => {
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

    socket.emit('ensure_topic_connections', {
      topicId: 'ops',
      members: ['alpha', 'beta'],
      chatMappings: {
        alpha: { chatId: 'chat-alpha', status: 'attached' },
        beta: { chatId: 'chat-beta', status: 'attached' }
      }
    })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(2))
    for (const upstream of FakeWebSocket.instances) upstream.open()
    socket.emit('send_group_message', {
      topicId: 'ops',
      text: 'hello group',
      media: [{ name: 'notes.txt', data_url: 'data:text/plain;base64,bm90ZXM=' }],
      memberIds: ['alpha', 'beta'],
      chatMappings: {
        alpha: { chatId: 'chat-alpha', status: 'attached' },
        beta: { chatId: 'chat-beta', status: 'attached' }
      }
    })

    await vi.waitFor(() => {
      expect(FakeWebSocket.instances[0].sent.at(-1)).toBe(JSON.stringify({ type: 'message', chat_id: 'chat-alpha', content: 'hello group', media: [{ name: 'notes.txt', data_url: 'data:text/plain;base64,bm90ZXM=' }] }))
      expect(FakeWebSocket.instances[1].sent.at(-1)).toBe(JSON.stringify({ type: 'message', chat_id: 'chat-beta', content: 'hello group', media: [{ name: 'notes.txt', data_url: 'data:text/plain;base64,bm90ZXM=' }] }))
    })
  })

  it('emits safe errors for invalid topic connection payloads', async () => {
    FakeWebSocket.instances = []
    const base = await listen()
    registerChatBridge(
      server!,
      { port: 6060, authToken: 'dashboard', instances: [] },
      { WebSocketImpl: FakeWebSocket }
    )
    const socket = connectChat(base, 'dashboard')
    await waitForEvent<void>(socket, 'connect')

    socket.emit('ensure_topic_connections', { topicId: '', members: 'alpha' })

    await expect(waitForEvent(socket, 'chat_event')).resolves.toEqual({ instanceId: '', event: 'error', chatId: '', detail: 'invalid chat payload' })
    expect(FakeWebSocket.instances).toHaveLength(0)
  })

  it('adds topic id to attached events correlated from pending new chats', async () => {
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
    const events: unknown[] = []
    socket.on('chat_event', (event) => events.push(event))

    socket.emit('ensure_topic_connections', { topicId: 'ops', members: ['alpha'], chatMappings: {} })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].open()
    FakeWebSocket.instances[0].emit('message', Buffer.from('{"event":"attached","chat_id":"chat-alpha"}'))

    await vi.waitFor(() => expect(events).toContainEqual({ topicId: 'ops', instanceId: 'alpha', event: 'attached', chatId: 'chat-alpha' }))
  })

  it('adds topic id to later upstream events for mapped chats', async () => {
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
    const events: unknown[] = []
    socket.on('chat_event', (event) => events.push(event))

    socket.emit('ensure_topic_connections', { topicId: 'ops', members: ['alpha'], chatMappings: { alpha: { chatId: 'chat-alpha', status: 'attached' } } })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].open()
    FakeWebSocket.instances[0].emit('message', Buffer.from('{"event":"delta","chat_id":"chat-alpha","text":"ops reply"}'))

    await vi.waitFor(() => expect(events).toContainEqual({ topicId: 'ops', instanceId: 'alpha', event: 'delta', chatId: 'chat-alpha', text: 'ops reply' }))
  })

  it('deduplicates repeated topic ensure requests before upstream open', async () => {
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

    socket.emit('ensure_topic_connections', { topicId: 'ops', members: ['alpha'], chatMappings: {} })
    socket.emit('ensure_topic_connections', { topicId: 'ops', members: ['alpha'], chatMappings: {} })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].open()

    await vi.waitFor(() => expect(FakeWebSocket.instances[0].sent).toEqual([JSON.stringify({ type: 'new_chat' })]))
  })

  it('rejects mapped sends that were never established for the socket topic', async () => {
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
    const events: unknown[] = []
    socket.on('chat_event', (event) => events.push(event))
    socket.emit('connect_group', { instanceIds: ['alpha'] })
    await vi.waitFor(() => expect(FakeWebSocket.instances).toHaveLength(1))
    FakeWebSocket.instances[0].open()

    socket.emit('send_group_message', {
      topicId: 'ops',
      text: 'forged',
      memberIds: ['alpha'],
      chatMappings: { alpha: { chatId: 'forged-chat', status: 'attached' } }
    })

    await vi.waitFor(() => expect(events).toContainEqual({ topicId: 'ops', instanceId: 'alpha', event: 'error', chatId: 'forged-chat', detail: 'not attached' }))
    expect(FakeWebSocket.instances[0].sent).toEqual([])
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
