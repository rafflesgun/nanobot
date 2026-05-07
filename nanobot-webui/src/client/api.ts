export type PublicInstance = {
  id: string
  name: string
  baseUrl: string
  enabled: boolean
}

export async function fetchInstances(token: string): Promise<PublicInstance[]> {
  const res = await fetch('/api/instances', { headers: { authorization: `Bearer ${token}` } })
  if (!res.ok) throw new Error(`failed to load instances: ${res.status}`)
  const payload = await res.json()
  return payload.instances
}
