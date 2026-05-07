import { io } from 'socket.io-client'

export type ChatEvent = {
  instanceId: string
  event: string
  chatId: string
  text?: string
  detail?: string
  reasoning?: string
  tool?: string
  tool_call?: string
}

export type ChatSocket = {
  on(event: 'chat_event', listener: (payload: ChatEvent) => void): unknown
  emit(event: 'connect_group', payload: { instanceIds: string[] }): unknown
  emit(event: 'send_group_message', payload: { text: string }): unknown
  disconnect(): unknown
}

export function createChatSocket(token: string): ChatSocket {
  return io('/chat', { auth: { token } })
}
