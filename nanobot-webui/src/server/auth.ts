import crypto from 'node:crypto'

export function isDashboardAuthorized(headers: Record<string, string | string[] | undefined>, token: string): boolean {
  const raw = headers.authorization
  const value = Array.isArray(raw) ? raw[0] : raw
  if (!value?.toLowerCase().startsWith('bearer ')) return false
  const supplied = value.slice(7).trim()
  const suppliedBuffer = Buffer.from(supplied)
  const tokenBuffer = Buffer.from(token)
  if (!supplied || suppliedBuffer.length !== tokenBuffer.length) return false
  return crypto.timingSafeEqual(suppliedBuffer, tokenBuffer)
}
