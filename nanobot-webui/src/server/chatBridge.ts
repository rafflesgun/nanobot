import type http from 'node:http'
import { Server as SocketIOServer } from 'socket.io'
import WebSocket from 'ws'
import { isDashboardAuthorized } from './auth.js'
import { websocketUrlForInstance, type WebuiConfig } from './config.js'

export type BrowserChatEvent = {
  topicId?: string
  instanceId: string
  event: string
  chatId: string
  text?: string
  detail?: string
  [key: string]: unknown
}

type ChatMapping = {
  chatId: string
  status?: string
  lastError?: string
}

type PendingAttach = {
  topicId: string
  chatId?: string
}

type ChatBridgeOptions = {
  WebSocketImpl?: WebSocketConstructor
}

type WebSocketLike = {
  close(): void
  on(event: 'message', listener: (data: WebSocket.RawData) => void): unknown
  on(event: 'open' | 'close' | 'error', listener: () => void): unknown
  readyState: number
  send(payload: string): void
}

type WebSocketConstructor = {
  new (url: string): WebSocketLike
}

function invalidPayload(instanceId = '', detail = 'invalid chat payload'): BrowserChatEvent {
  return { instanceId, event: 'error', chatId: '', detail }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
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
    const upstreams = new Map<string, WebSocketLike>()
    const pendingAttachByInstance = new Map<string, PendingAttach[]>()
    const topicByInstanceChat = new Map<string, string>()
    let generation = 0

    function closeUpstreams() {
      for (const upstream of upstreams.values()) upstream.close()
      upstreams.clear()
    }

    function connectUpstream(instanceId: string, currentGeneration: number) {
      const instance = config.instances.find((item) => item.id === instanceId)
      if (!instance) {
        socket.emit('chat_event', { instanceId, event: 'error', chatId: '', detail: 'unknown instance' })
        return
      }
      if (!instance.enabled) {
        socket.emit('chat_event', { instanceId, event: 'error', chatId: '', detail: 'instance disabled' })
        return
      }
      let upstream: WebSocketLike
      try {
        upstream = new WebSocketImpl(websocketUrlForInstance(instance))
      } catch {
        socket.emit('chat_event', { instanceId, event: 'error', chatId: '', detail: 'chat.connection_failed' })
        return
      }
      upstreams.set(instanceId, upstream)
      socket.emit('chat_event', { instanceId, event: 'chat.connecting', chatId: '' })
      upstream.on('open', () => {
        if (currentGeneration !== generation || upstreams.get(instanceId) !== upstream) return
        socket.emit('chat_event', { instanceId, event: 'chat.connected', chatId: '' })
      })
      upstream.on('message', (data) => {
        if (currentGeneration !== generation || upstreams.get(instanceId) !== upstream) return
        const event = normalizeNanobotEvent(instanceId, data.toString())
        const pending = event.event === 'attached' ? matchingPendingAttach(instanceId, event.chatId) : undefined
        if (pending) topicByInstanceChat.set(mappingKey(instanceId, event.chatId), pending.topicId)
        const topicId = pending?.topicId ?? topicByInstanceChat.get(mappingKey(instanceId, event.chatId))
        socket.emit('chat_event', topicId ? { ...event, topicId } : event)
      })
      upstream.on('close', () => {
        if (currentGeneration !== generation || upstreams.get(instanceId) !== upstream) return
        socket.emit('chat_event', { instanceId, event: 'chat.disconnected', chatId: '' })
      })
      upstream.on('error', () => {
        if (currentGeneration !== generation || upstreams.get(instanceId) !== upstream) return
        socket.emit('chat_event', { instanceId, event: 'chat.connection_failed', chatId: '' })
      })
    }

    function openOrConnect(instanceId: string, currentGeneration: number) {
      const existing = upstreams.get(instanceId)
      if (existing) return existing
      connectUpstream(instanceId, currentGeneration)
      return upstreams.get(instanceId)
    }

    function sendWhenOpen(upstream: WebSocketLike, payload: unknown) {
      const message = JSON.stringify(payload)
      if (upstream.readyState === WebSocket.OPEN) {
        upstream.send(message)
        return
      }
      upstream.on('open', () => upstream.send(message))
    }

    function queuePendingAttach(instanceId: string, pending: PendingAttach) {
      const queue = pendingAttachByInstance.get(instanceId) ?? []
      const duplicate = queue.some((item) => item.topicId === pending.topicId && item.chatId === pending.chatId)
      if (duplicate) return false
      queue.push(pending)
      pendingAttachByInstance.set(instanceId, queue)
      return true
    }

    function matchingPendingAttach(instanceId: string, chatId: string) {
      const queue = pendingAttachByInstance.get(instanceId) ?? []
      const mappedIndex = queue.findIndex((item) => item.chatId === chatId)
      const index = mappedIndex >= 0 ? mappedIndex : queue.findIndex((item) => !item.chatId)
      if (index < 0) return undefined
      const [pending] = queue.splice(index, 1)
      if (queue.length === 0) pendingAttachByInstance.delete(instanceId)
      else pendingAttachByInstance.set(instanceId, queue)
      return pending
    }

    function mappingKey(instanceId: string, chatId: string) {
      return `${instanceId}\u0000${chatId}`
    }

    function sendToOpenUpstreams(payload: unknown) {
      const message = JSON.stringify(payload)
      for (const upstream of upstreams.values()) {
        if (upstream.readyState === WebSocket.OPEN) upstream.send(message)
      }
    }

    socket.on('ensure_topic_connections', (payload: unknown) => {
      if (!isRecord(payload)) {
        socket.emit('chat_event', invalidPayload())
        return
      }
      const { topicId, members, chatMappings } = payload
      if (typeof topicId !== 'string' || !topicId || !Array.isArray(members)) {
        socket.emit('chat_event', invalidPayload())
        return
      }
      const mappings = isRecord(chatMappings) ? chatMappings : {}
      const currentGeneration = generation
      for (const member of new Set(members)) {
        if (typeof member !== 'string' || !member) {
          socket.emit('chat_event', invalidPayload())
          return
        }
        const upstream = openOrConnect(member, currentGeneration)
        if (!upstream) continue
        const mapping = isRecord(mappings[member]) ? (mappings[member] as Partial<ChatMapping>) : undefined
        if (typeof mapping?.chatId === 'string' && mapping.chatId) {
          if (topicByInstanceChat.get(mappingKey(member, mapping.chatId)) === topicId) continue
          if (!queuePendingAttach(member, { topicId, chatId: mapping.chatId })) continue
          topicByInstanceChat.set(mappingKey(member, mapping.chatId), topicId)
          sendWhenOpen(upstream, { type: 'attach', chat_id: mapping.chatId })
        } else {
          if (!queuePendingAttach(member, { topicId })) continue
          sendWhenOpen(upstream, { type: 'new_chat' })
        }
      }
    })

    socket.on('send_group_message', (payload: unknown) => {
      if (!isRecord(payload)) {
        socket.emit('chat_event', invalidPayload())
        return
      }
      const { topicId, text, media, memberIds, chatMappings } = payload
      if (typeof topicId !== 'string' || !topicId || typeof text !== 'string' || !Array.isArray(memberIds)) {
        socket.emit('chat_event', invalidPayload())
        return
      }
      const mappings = isRecord(chatMappings) ? chatMappings : {}
      for (const memberId of memberIds) {
        if (typeof memberId !== 'string' || !memberId) {
          socket.emit('chat_event', invalidPayload())
          return
        }
        const mapping = isRecord(mappings[memberId]) ? (mappings[memberId] as Partial<ChatMapping>) : undefined
        if (typeof mapping?.chatId !== 'string' || !mapping.chatId) {
          socket.emit('chat_event', { topicId, instanceId: memberId, event: 'error', chatId: '', detail: 'not attached' })
          continue
        }
        if (topicByInstanceChat.get(mappingKey(memberId, mapping.chatId)) !== topicId) {
          socket.emit('chat_event', { topicId, instanceId: memberId, event: 'error', chatId: mapping.chatId, detail: 'not attached' })
          continue
        }
        const upstream = upstreams.get(memberId)
        if (!upstream || upstream.readyState !== WebSocket.OPEN) {
          socket.emit('chat_event', { topicId, instanceId: memberId, event: 'error', chatId: mapping.chatId, detail: 'not connected' })
          continue
        }
        upstream.send(JSON.stringify({
          type: 'message',
          chat_id: mapping.chatId,
          content: text,
          ...(Array.isArray(media) && media.length > 0 ? { media } : {})
        }))
      }
    })

    socket.on('connect_instance', (payload: unknown) => {
      const currentGeneration = ++generation
      closeUpstreams()
      if (!payload || typeof payload !== 'object') {
        socket.emit('chat_event', invalidPayload('', 'invalid connect payload'))
        return
      }
      const { instanceId } = payload as { instanceId?: unknown }
      if (typeof instanceId !== 'string' || !instanceId) {
        socket.emit('chat_event', invalidPayload(typeof instanceId === 'string' ? instanceId : '', 'invalid connect payload'))
        return
      }
      connectUpstream(instanceId, currentGeneration)
    })

    socket.on('connect_group', (payload: unknown) => {
      const currentGeneration = ++generation
      closeUpstreams()
      if (!payload || typeof payload !== 'object') {
        socket.emit('chat_event', invalidPayload('', 'invalid connect payload'))
        return
      }
      const { instanceIds } = payload as { instanceIds?: unknown }
      if (!Array.isArray(instanceIds) || instanceIds.some((instanceId) => typeof instanceId !== 'string' || !instanceId)) {
        socket.emit('chat_event', invalidPayload('', 'invalid connect payload'))
        return
      }
      for (const instanceId of new Set(instanceIds)) connectUpstream(instanceId, currentGeneration)
    })

    socket.on('send_message', (payload) => {
      sendToOpenUpstreams(payload)
    })

    socket.on('disconnect', () => {
      generation++
      closeUpstreams()
    })
  })

  return io
}
