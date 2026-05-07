import { describe, expect, it } from 'vitest'
import { appendOutboundMessage, applyChatEvent, createTranscriptState } from './chatTranscript'

describe('chatTranscript', () => {
  it('merges delta chunks into one assistant entry per instance and chat', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'hello ' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'world' }, 'Alpha')

    expect(state.entries).toEqual([
      { id: 1, instanceId: 'alpha', chatId: 'c1', label: 'Alpha', role: 'assistant', event: 'delta', text: 'hello world' }
    ])
  })

  it('keeps terminal stream events out of the visible transcript but stores raw debug events', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'stream_end', chatId: 'c1' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'turn_end', chatId: 'c1' }, 'Alpha')

    expect(state.entries).toEqual([])
    expect(state.debugEvents).toEqual([
      { instanceId: 'alpha', event: 'stream_end', chatId: 'c1' },
      { instanceId: 'alpha', event: 'turn_end', chatId: 'c1' }
    ])
  })

  it('adds visible system messages for errors and outbound user messages', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'error', chatId: '', detail: 'bad frame' }, 'Alpha')
    appendOutboundMessage(state, 'hello bots')

    expect(state.entries).toEqual([
      { id: 1, instanceId: 'alpha', chatId: '', label: 'Alpha', role: 'system', event: 'error', text: 'bad frame' },
      { id: 2, instanceId: 'local', chatId: '', label: 'You', role: 'user', event: 'outbound', text: 'hello bots' }
    ])
  })
})
