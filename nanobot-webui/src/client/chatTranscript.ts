import type { ChatEvent } from './socket'

export type TranscriptRole = 'assistant' | 'system' | 'user'
export type TranscriptKind = 'message' | 'tool' | 'reasoning' | 'subagent'

export type ComposerMedia = {
  data_url: string
  name?: string
}

export type TranscriptEntry = {
  id: number
  instanceId: string
  chatId: string
  label: string
  role: TranscriptRole
  kind?: TranscriptKind
  event: string
  text: string
  title?: string
  attachments?: ComposerMedia[]
  timestamp?: number
  streamId?: string
  turnId?: string
  status?: string
  name?: string
}

export type TranscriptState = {
  entries: TranscriptEntry[]
  debugEvents: ChatEvent[]
  nextEntryId: number
  streamingKeys: Set<string>
  legacyParserByStream?: Record<string, { buffer: string; mode: 'message' | 'reasoning' }>
}

const HIDDEN_EVENTS = new Set(['stream_end', 'turn_end', 'chat.connecting', 'chat.connected', 'chat.disconnected', 'attached'])

const THINK_OPEN = '\u003Cthink\u003E'
const THINK_CLOSE = '\u003C/think\u003E'

export function createTranscriptState(): TranscriptState {
  return { entries: [], debugEvents: [], nextEntryId: 1, streamingKeys: new Set(), legacyParserByStream: {} }
}

function streamingKey(instanceId: string, chatId: string): string {
  return `${instanceId}\0${chatId}`
}

export function appendOutboundMessage(state: TranscriptState, text: string, attachments: ComposerMedia[] = []) {
  state.entries.push({
    id: state.nextEntryId++,
    instanceId: 'local',
    chatId: '',
    label: 'You',
    role: 'user',
    event: 'outbound',
    text,
    timestamp: Date.now(),
    ...(attachments.length > 0 ? { attachments: [...attachments] } : {})
  })
}

function isSetLike(value: unknown): value is Set<string> {
  if (value instanceof Set) return true
  if (value && typeof value === 'object' && typeof (value as any).has === 'function' && typeof (value as any).add === 'function' && typeof (value as any).delete === 'function') return true
  return false
}

function ensureStreamingKeys(state: TranscriptState): Set<string> {
  if (isSetLike(state.streamingKeys)) return state.streamingKeys
  state.streamingKeys = new Set()
  return state.streamingKeys
}

export function normalizeTranscriptState(state: TranscriptState): TranscriptState {
  if (!Array.isArray(state.entries)) state.entries = []
  if (!Array.isArray(state.debugEvents)) state.debugEvents = []
  if (typeof state.nextEntryId !== 'number') state.nextEntryId = 1
  ensureStreamingKeys(state)
  if (!state.legacyParserByStream || typeof state.legacyParserByStream !== 'object') state.legacyParserByStream = {}
  return state
}

function eventKind(event: ChatEvent): TranscriptKind {
  const name = event.event.toLowerCase()
  if (event.kind === 'tool' || event.tool || event.tool_call || name.includes('tool')) return 'tool'
  if (event.kind === 'subagent' || name.includes('subagent')) return 'subagent'
  if (event.kind === 'reasoning' || event.reasoning || name.includes('reasoning')) return 'reasoning'
  return 'message'
}

function eventStreamId(event: ChatEvent, kind: TranscriptKind): string {
  return event.stream_id ?? `${event.instanceId}\0${event.chatId}\0${kind}`
}

function findLastStreamEntry(state: TranscriptState, event: ChatEvent, kind: TranscriptKind): TranscriptEntry | undefined {
  const streamId = eventStreamId(event, kind)
  return [...state.entries].reverse().find((entry) =>
    entry.instanceId === event.instanceId &&
    entry.chatId === event.chatId &&
    entry.kind === kind &&
    entry.streamId === streamId
  )
}

function textFromEvent(event: ChatEvent) {
  return event.text ?? event.detail ?? event.reasoning ?? event.tool_call ?? ''
}

function toolTitle(event: ChatEvent) {
  const n = event.name ?? event.tool
  return n ? `Tool: ${n}` : 'Tool call'
}

function subagentTitle(event: ChatEvent) {
  const n = event.subagent_name ?? event.name
  return n ? `Sub-agent: ${n}` : 'Sub-agent'
}

function appendStreamSegment(state: TranscriptState, event: ChatEvent, label: string, kind: TranscriptKind, text: string, eventName: string) {
  if (!text) return
  const streamId = eventStreamId(event, kind)
  const legacyKey = !event.stream_id ? streamingKey(event.instanceId, event.chatId) + '\0' + kind : ''
  const keys = ensureStreamingKeys(state)
  const hasActiveStream = legacyKey ? keys.has(legacyKey) : true
  const existing = hasActiveStream ? [...state.entries].reverse().find((entry) =>
    entry.instanceId === event.instanceId &&
    entry.chatId === event.chatId &&
    entry.kind === kind &&
    entry.streamId === streamId &&
    entry.event === eventName
  ) : undefined
  if (existing) {
    if (kind === 'tool' || kind === 'subagent') {
      existing.text += `${existing.text && text ? '\n' : ''}${text}`
    } else {
      existing.text += text
    }
    return
  }
  if (legacyKey) keys.add(legacyKey)
  state.entries.push({
    id: state.nextEntryId++,
    instanceId: event.instanceId,
    chatId: event.chatId,
    label,
    role: kind === 'tool' ? 'system' : 'assistant',
    kind,
    event: eventName,
    text,
    title: kind === 'reasoning' ? 'Thinking' : kind === 'tool' ? toolTitle(event) : kind === 'subagent' ? subagentTitle(event) : undefined,
    timestamp: Date.now(),
    streamId,
    turnId: event.turn_id,
    status: event.status,
    name: event.name ?? event.subagent_name,
  })
}

type LegacySegment = { kind: TranscriptKind; text: string }

function longestSuffixPrefix(text: string, target: string): string {
  const max = Math.min(text.length, target.length - 1)
  for (let len = max; len > 0; len--) {
    const suffix = text.slice(-len)
    if (target.startsWith(suffix)) return suffix
  }
  return ''
}

function parseLegacyThinkSegments(state: TranscriptState, event: ChatEvent): LegacySegment[] {
  const key = event.stream_id ?? `${event.instanceId}\0${event.chatId}\0legacy`
  const parsers = state.legacyParserByStream ?? (state.legacyParserByStream = {})
  const parser = parsers[key] ?? (parsers[key] = { buffer: '', mode: 'message' as const })
  parser.buffer += event.text ?? ''

  const segments: LegacySegment[] = []
  while (parser.buffer.length > 0) {
    if (parser.mode === 'message') {
      const start = parser.buffer.indexOf(THINK_OPEN)
      if (start < 0) {
        const partial = longestSuffixPrefix(parser.buffer, THINK_OPEN)
        const emitText = parser.buffer.slice(0, parser.buffer.length - partial.length)
        if (emitText) segments.push({ kind: 'message', text: emitText })
        parser.buffer = partial
        break
      }
      const before = parser.buffer.slice(0, start)
      if (before) segments.push({ kind: 'message', text: before })
      parser.buffer = parser.buffer.slice(start + THINK_OPEN.length)
      parser.mode = 'reasoning'
      continue
    }

    const end = parser.buffer.indexOf(THINK_CLOSE)
    if (end < 0) {
      const partial = longestSuffixPrefix(parser.buffer, THINK_CLOSE)
      const emitText = parser.buffer.slice(0, parser.buffer.length - partial.length)
      if (emitText) segments.push({ kind: 'reasoning', text: emitText })
      parser.buffer = partial
      break
    }
    const thought = parser.buffer.slice(0, end)
    if (thought) segments.push({ kind: 'reasoning', text: thought })
    parser.buffer = parser.buffer.slice(end + THINK_CLOSE.length)
    parser.mode = 'message'
  }
  return segments
}

export function applyChatEvent(state: TranscriptState, event: ChatEvent, label: string) {
  if (!Array.isArray(state.debugEvents)) state.debugEvents = []
  state.debugEvents.push(event)

  if (event.event === 'stream_end' || event.event === 'turn_end') {
    const keys = ensureStreamingKeys(state)
    const base = streamingKey(event.instanceId, event.chatId)
    keys.delete(base)
    const toDelete = [...keys].filter(k => k.startsWith(base))
    for (const k of toDelete) keys.delete(k)
    ensureStreamingKeys(state).delete(streamingKey(event.instanceId, event.chatId))
    return
  }

  if (HIDDEN_EVENTS.has(event.event)) return

  if (event.event.endsWith('.start') || event.event.endsWith('.end')) {
    const kind = eventKind(event)
    const text = textFromEvent(event)
    const streamId = eventStreamId(event, kind)
    const existing = findLastStreamEntry(state, event, kind)
    if (existing) {
      if (text) existing.text += `${existing.text ? '\n' : ''}${text}`
      existing.status = event.status ?? existing.status
      existing.event = event.event
      return
    }
    state.entries.push({
      id: state.nextEntryId++,
      instanceId: event.instanceId,
      chatId: event.chatId,
      label,
      role: kind === 'tool' ? 'system' : 'assistant',
      kind,
      event: event.event,
      text,
      title: kind === 'reasoning' ? 'Thinking' : kind === 'tool' ? toolTitle(event) : kind === 'subagent' ? subagentTitle(event) : undefined,
      timestamp: Date.now(),
      streamId,
      turnId: event.turn_id,
      status: event.status,
      name: event.name ?? event.subagent_name,
    })
    return
  }

  if (event.event.endsWith('.delta')) {
    const kind = eventKind(event)
    const existing = findLastStreamEntry(state, event, kind)
    if (existing) {
      const nextText = textFromEvent(event)
      if (kind === 'tool' || kind === 'subagent') {
        existing.text += `${existing.text && nextText ? '\n' : ''}${nextText}`
      } else {
        existing.text += nextText
      }
      existing.status = event.status ?? existing.status
      return
    }
    state.entries.push({
      id: state.nextEntryId++,
      instanceId: event.instanceId,
      chatId: event.chatId,
      label,
      role: kind === 'tool' ? 'system' : 'assistant',
      kind,
      event: event.event,
      text: textFromEvent(event),
      title: kind === 'reasoning' ? 'Thinking' : kind === 'tool' ? toolTitle(event) : kind === 'subagent' ? subagentTitle(event) : undefined,
      timestamp: Date.now(),
      streamId: eventStreamId(event, kind),
      turnId: event.turn_id,
      status: event.status,
      name: event.name ?? event.subagent_name,
    })
    return
  }

  if (event.event === 'delta') {
    const segments = parseLegacyThinkSegments(state, event)
    for (const segment of segments) {
      appendStreamSegment(state, event, label, segment.kind, segment.text, event.event)
    }
    return
  }

  const kind = classifyLegacyEvent(event)
  if (kind !== 'message') {
    state.entries.push({
      id: state.nextEntryId++,
      instanceId: event.instanceId,
      chatId: event.chatId,
      label,
      role: kind === 'tool' ? 'system' : 'assistant',
      kind,
      event: event.event,
      text: textFromEvent(event),
      title: kind === 'tool' ? toolTitle(event) : 'Thinking',
      timestamp: Date.now(),
    })
    return
  }

  const rawText = textFromEvent(event)
  const segments = splitCompleteThinkSegments(rawText)
  if (segments.length === 0) return
  if (segments.length === 1 && segments[0].kind === 'message') {
    state.entries.push({
      id: state.nextEntryId++,
      instanceId: event.instanceId,
      chatId: event.chatId,
      label,
      role: event.event === 'error' || event.detail ? 'system' : 'assistant',
      event: event.event,
      text: rawText,
      timestamp: Date.now(),
    })
    return
  }
  for (const segment of segments) {
    if (!segment.text) continue
    state.entries.push({
      id: state.nextEntryId++,
      instanceId: event.instanceId,
      chatId: event.chatId,
      label,
      role: segment.kind === 'reasoning' ? 'assistant' : (event.event === 'error' || event.detail ? 'system' : 'assistant'),
      kind: segment.kind,
      event: event.event,
      text: segment.text,
      title: segment.kind === 'reasoning' ? 'Thinking' : undefined,
      timestamp: Date.now(),
    })
  }
}

function splitCompleteThinkSegments(text: string): LegacySegment[] {
  if (!text.includes(THINK_OPEN)) return [{ kind: 'message', text }]
  const segments: LegacySegment[] = []
  let remaining = text
  while (remaining.length > 0) {
    const start = remaining.indexOf(THINK_OPEN)
    if (start < 0) {
      if (remaining) segments.push({ kind: 'message', text: remaining })
      break
    }
    if (start > 0) segments.push({ kind: 'message', text: remaining.slice(0, start) })
    const afterOpen = remaining.slice(start + THINK_OPEN.length)
    const end = afterOpen.indexOf(THINK_CLOSE)
    if (end < 0) {
      segments.push({ kind: 'reasoning', text: afterOpen })
      break
    }
    segments.push({ kind: 'reasoning', text: afterOpen.slice(0, end) })
    remaining = afterOpen.slice(end + THINK_CLOSE.length)
  }
  return segments
}

function classifyLegacyEvent(event: ChatEvent): TranscriptKind {
  const name = event.event.toLowerCase()
  if (event.tool || event.tool_call || name.includes('tool')) return 'tool'
  if (event.reasoning || name.includes('reasoning')) return 'reasoning'
  return 'message'
}
