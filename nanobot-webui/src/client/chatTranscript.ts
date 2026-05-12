import type { ChatEvent } from './socket'

export type TranscriptRole = 'assistant' | 'system' | 'user'
export type TranscriptKind = 'message' | 'tool' | 'reasoning'

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
}

export type TranscriptState = {
  entries: TranscriptEntry[]
  debugEvents: ChatEvent[]
  nextEntryId: number
  streamingKeys: Set<string>
}

const HIDDEN_EVENTS = new Set(['stream_end', 'turn_end', 'chat.connecting', 'chat.connected', 'chat.disconnected', 'attached'])

export function createTranscriptState(): TranscriptState {
  return { entries: [], debugEvents: [], nextEntryId: 1, streamingKeys: new Set() }
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

export function applyChatEvent(state: TranscriptState, event: ChatEvent, label: string) {
  state.debugEvents.push(event)

  if (event.event === 'stream_end' || event.event === 'turn_end') {
    ;(state.streamingKeys ?? (state.streamingKeys = new Set())).delete(streamingKey(event.instanceId, event.chatId))
    return
  }

  if (HIDDEN_EVENTS.has(event.event)) return

  const kind = classifyEvent(event)
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
      title: kind === 'tool' ? toolTitle(event) : 'Reasoning',
      timestamp: Date.now(),
    })
    return
  }

  if (event.event === 'delta') {
    const key = streamingKey(event.instanceId, event.chatId)
    const keys = state.streamingKeys ?? (state.streamingKeys = new Set())
    if (keys.has(key)) {
      const existing = state.entries.find(
        (entry) => entry.role === 'assistant' && entry.instanceId === event.instanceId && entry.chatId === event.chatId && entry.event === 'delta'
      )
      if (existing) {
        existing.text += event.text ?? ''
        return
      }
    }
    state.streamingKeys.add(key)
    state.entries.push({
      id: state.nextEntryId++,
      instanceId: event.instanceId,
      chatId: event.chatId,
      label,
      role: 'assistant',
      event: event.event,
      text: event.text ?? '',
      timestamp: Date.now(),
    })
    return
  }

  state.entries.push({
    id: state.nextEntryId++,
    instanceId: event.instanceId,
    chatId: event.chatId,
    label,
    role: event.event === 'error' || event.detail ? 'system' : 'assistant',
    event: event.event,
    text: textFromEvent(event),
    timestamp: Date.now(),
  })
}

function classifyEvent(event: ChatEvent): TranscriptKind {
  const name = event.event.toLowerCase()
  if (event.tool || event.tool_call || name.includes('tool')) return 'tool'
  if (event.reasoning || name.includes('reasoning')) return 'reasoning'
  return 'message'
}

function textFromEvent(event: ChatEvent) {
  return event.text ?? event.detail ?? event.reasoning ?? event.tool_call ?? ''
}

function toolTitle(event: ChatEvent) {
  return event.tool ? `Tool: ${event.tool}` : 'Tool call'
}
