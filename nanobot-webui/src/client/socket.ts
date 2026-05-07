import { io, type Socket } from 'socket.io-client'

export type ChatEvent = {
  instanceId: string
  event: string
  chatId: string
  text?: string
  detail?: string
}

export type ChatSocket = Pick<Socket, 'on' | 'emit' | 'disconnect'>

export function createChatSocket(token: string): ChatSocket {
  return io('/chat', { auth: { token } })
}
