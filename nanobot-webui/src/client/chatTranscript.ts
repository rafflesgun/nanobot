import type { ChatEvent } from './socket'

export type TranscriptRole = 'assistant' | 'system' | 'user'
export type TranscriptKind = 'message' | 'tool' | 'reasoning'

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
}

export type TranscriptState = {
  entries: TranscriptEntry[]
  debugEvents: ChatEvent[]
  nextEntryId: number
}

const HIDDEN_EVENTS = new Set(['stream_end', 'turn_end', 'chat.connecting', 'chat.connected', 'chat.disconnected'])

export function createTranscriptState(): TranscriptState {
  return { entries: [], debugEvents: [], nextEntryId: 1 }
}

export function appendOutboundMessage(state: TranscriptState, text: string) {
  state.entries.push({
    id: state.nextEntryId++,
    instanceId: 'local',
    chatId: '',
    label: 'You',
    role: 'user',
    event: 'outbound',
    text
  })
}

export function applyChatEvent(state: TranscriptState, event: ChatEvent, label: string) {
  state.debugEvents.push(event)
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
      title: kind === 'tool' ? toolTitle(event) : 'Reasoning'
    })
    return
  }

  if (event.event === 'delta') {
    const existing = state.entries.find(
      (entry) => entry.role === 'assistant' && entry.instanceId === event.instanceId && entry.chatId === event.chatId
    )
    if (existing) {
      existing.text += event.text ?? ''
      return
    }
    state.entries.push({
      id: state.nextEntryId++,
      instanceId: event.instanceId,
      chatId: event.chatId,
      label,
      role: 'assistant',
      event: event.event,
      text: event.text ?? ''
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
    text: textFromEvent(event)
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
