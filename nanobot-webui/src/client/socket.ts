import { io } from 'socket.io-client'

export function createChatSocket(token: string) {
  return io('/chat', { auth: { token } })
}
