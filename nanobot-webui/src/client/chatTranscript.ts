import type { ChatEvent } from './socket'

export type TranscriptRole = 'assistant' | 'system' | 'user'

export type TranscriptEntry = {
  id: number
  instanceId: string
  chatId: string
  label: string
  role: TranscriptRole
  event: string
  text: string
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
    text: event.text ?? event.detail ?? ''
  })
}
