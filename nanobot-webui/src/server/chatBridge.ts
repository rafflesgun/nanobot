import type http from 'node:http'
import { Server as SocketIOServer } from 'socket.io'
import WebSocket from 'ws'
import { isDashboardAuthorized } from './auth.js'
import { websocketUrlForInstance, type WebuiConfig } from './config.js'

export type BrowserChatEvent = {
  instanceId: string
  event: string
  chatId: string
  text?: string
  detail?: string
  [key: string]: unknown
}

type ChatBridgeOptions = {
  WebSocketImpl?: WebSocketConstructor
}

type WebSocketLike = {
  close(): void
  on(event: 'message', listener: (data: WebSocket.RawData) => void): unknown
  on(event: 'close' | 'error', listener: () => void): unknown
  readyState: number
  send(payload: string): void
}

type WebSocketConstructor = {
  new (url: string): WebSocketLike
}

function invalidConnectPayload(instanceId = ''): BrowserChatEvent {
  return { instanceId, event: 'error', chatId: '', detail: 'invalid connect payload' }
}

export function normalizeNanobotEvent(instanceId: string, raw: string): BrowserChatEvent {
  try {
    const parsed = JSON.parse(raw)
    const { chat_id, ...rest } = parsed
    return {
      ...rest,
      instanceId,
      chatId: typeof chat_id === 'string' ? chat_id : ''
    }
  } catch {
    return { instanceId, event: 'error', chatId: '', detail: 'invalid upstream frame' }
  }
}

export function registerChatBridge(server: http.Server, config: WebuiConfig, options: ChatBridgeOptions = {}): SocketIOServer {
  const WebSocketImpl = options.WebSocketImpl ?? WebSocket
  const io = new SocketIOServer(server, { path: '/socket.io' })
  const namespace = io.of('/chat')

  namespace.use((socket, next) => {
    const headers = socket.handshake.headers as Record<string, string | string[] | undefined>
    const token = socket.handshake.auth?.token
    const authorizedByHeader = isDashboardAuthorized(headers, config.authToken)
    const authorizedBySocketAuth =
      typeof token === 'string' && isDashboardAuthorized({ authorization: `Bearer ${token}` }, config.authToken)
    if (!authorizedByHeader && !authorizedBySocketAuth) {
      next(new Error('Unauthorized'))
      return
    }
    next()
  })

  namespace.on('connection', (socket) => {
    let upstream: WebSocketLike | undefined
    let generation = 0

    socket.on('connect_instance', (payload: unknown) => {
      const currentGeneration = ++generation
      upstream?.close()
      upstream = undefined

      if (!payload || typeof payload !== 'object') {
        socket.emit('chat_event', invalidConnectPayload())
        return
      }
      const { instanceId } = payload as { instanceId?: unknown }
      if (typeof instanceId !== 'string' || !instanceId) {
        socket.emit('chat_event', invalidConnectPayload(typeof instanceId === 'string' ? instanceId : ''))
        return
      }
      const instance = config.instances.find((item) => item.id === instanceId)
      if (!instance) {
        socket.emit('chat_event', { instanceId, event: 'error', chatId: '', detail: 'unknown instance' })
        return
      }
      if (!instance.enabled) {
        socket.emit('chat_event', { instanceId, event: 'error', chatId: '', detail: 'instance disabled' })
        return
      }
      try {
        upstream = new WebSocketImpl(websocketUrlForInstance(instance))
      } catch {
        socket.emit('chat_event', { instanceId, event: 'error', chatId: '', detail: 'chat.connection_failed' })
        return
      }
      upstream.on('message', (data) => {
        if (currentGeneration !== generation) return
        socket.emit('chat_event', normalizeNanobotEvent(instanceId, data.toString()))
      })
      upstream.on('close', () => {
        if (currentGeneration !== generation) return
        socket.emit('chat_event', { instanceId, event: 'chat.disconnected', chatId: '' })
      })
      upstream.on('error', () => {
        if (currentGeneration !== generation) return
        socket.emit('chat_event', { instanceId, event: 'chat.connection_failed', chatId: '' })
      })
    })

    socket.on('send_message', (payload) => {
      if (upstream?.readyState === WebSocket.OPEN) upstream.send(JSON.stringify(payload))
    })

    socket.on('disconnect', () => {
      generation++
      upstream?.close()
      upstream = undefined
    })
  })

  return io
}
