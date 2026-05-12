import { io } from 'socket.io-client'
import type { ChatMapping, ComposerMedia } from './api'

export type ChatEvent = {
  topicId?: string
  instanceId: string
  event: string
  chatId: string
  text?: string
  detail?: string
  reasoning?: string
  tool?: string
  tool_call?: string
  kind?: 'message' | 'reasoning' | 'tool' | 'subagent' | 'progress' | string
  stream_id?: string
  turn_id?: string
  name?: string
  status?: string
  tool_call_id?: string
  subagent_name?: string
}

export type EnsureTopicConnectionsPayload = {
  topicId: string
  members: string[]
  chatMappings: Record<string, ChatMapping>
}

export type SendGroupMessagePayload = {
  topicId: string
  text: string
  media?: ComposerMedia[]
  memberIds: string[]
  chatMappings: Record<string, ChatMapping>
}

export type ChatSocket = {
  on(event: 'chat_event', listener: (payload: ChatEvent) => void): unknown
  emit(event: 'connect_group', payload: { instanceIds: string[] }): unknown
  emit(event: 'ensure_topic_connections', payload: EnsureTopicConnectionsPayload): unknown
  emit(event: 'send_group_message', payload: SendGroupMessagePayload): unknown
  disconnect(): unknown
}

export function createChatSocket(token: string): ChatSocket {
  return io('/chat', { auth: { token } })
}
