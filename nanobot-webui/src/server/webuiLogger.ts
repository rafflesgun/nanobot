export type WebuiLogEntry = {
  at: string
  level: 'info' | 'error'
  method?: string
  path?: string
  status?: number
  message?: string
}

export type WebuiLogger = {
  info(entry: Omit<WebuiLogEntry, 'at' | 'level'>): void
  error(entry: Omit<WebuiLogEntry, 'at' | 'level'>): void
  list(): WebuiLogEntry[]
}

export function createWebuiLogger(limit = 200): WebuiLogger {
  const entries: WebuiLogEntry[] = []
  function append(level: WebuiLogEntry['level'], entry: Omit<WebuiLogEntry, 'at' | 'level'>) {
    entries.push({ at: new Date().toISOString(), level, ...entry })
    if (entries.length > limit) entries.splice(0, entries.length - limit)
  }
  return {
    info: (entry) => append('info', entry),
    error: (entry) => append('error', entry),
    list: () => [...entries]
  }
}
