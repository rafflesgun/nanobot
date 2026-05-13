import { describe, expect, it } from 'vitest'
import { appendOutboundMessage, applyChatEvent, createTranscriptState, normalizeTranscriptState } from './chatTranscript'

describe('chatTranscript', () => {
  it('merges delta chunks into one assistant entry per instance and chat', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'hello ' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'world' }, 'Alpha')

    expect(state.entries).toEqual([
      { id: 1, instanceId: 'alpha', chatId: 'c1', label: 'Alpha', role: 'assistant', kind: 'message', event: 'delta', text: 'hello world', timestamp: expect.any(Number), streamId: 'alpha\0c1\0message', title: undefined, turnId: undefined, status: undefined, name: undefined }
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
      { id: 1, instanceId: 'alpha', chatId: '', label: 'Alpha', role: 'system', event: 'error', text: 'bad frame', timestamp: expect.any(Number) },
      { id: 2, instanceId: 'local', chatId: '', label: 'You', role: 'user', event: 'outbound', text: 'hello bots', timestamp: expect.any(Number) }
    ])
  })

  it('stores outbound attachment metadata with user messages', () => {
    const state = createTranscriptState()

    appendOutboundMessage(state, 'see attachment', [{ name: 'notes.txt', data_url: 'data:text/plain;base64,bm90ZXM=' }])

    expect(state.entries[0]).toMatchObject({
      role: 'user',
      text: 'see attachment',
      attachments: [{ name: 'notes.txt', data_url: 'data:text/plain;base64,bm90ZXM=' }]
    })
  })

  it('classifies tool events as distinct transcript entries', () => {
    const state = createTranscriptState()

    applyChatEvent(
      state,
      { instanceId: 'alpha', event: 'tool_call.delta', chatId: 'c1', tool: 'search', detail: 'looking up docs' },
      'Alpha'
    )

    expect(state.entries).toMatchObject([
      {
        instanceId: 'alpha',
        chatId: 'c1',
        label: 'Alpha',
        role: 'system',
        kind: 'tool',
        event: 'tool_call.delta',
        text: 'looking up docs',
        title: 'Tool: search',
      }
    ])
  })

  it('classifies reasoning events as distinct transcript entries', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'reasoning.delta', chatId: 'c1', reasoning: 'checking facts' }, 'Alpha')

    expect(state.entries).toMatchObject([
      {
        instanceId: 'alpha',
        chatId: 'c1',
        label: 'Alpha',
        role: 'assistant',
        kind: 'reasoning',
        event: 'reasoning.delta',
        text: 'checking facts',
        title: 'Thinking',
      }
    ])
  })

  it('classifies reasoning events as distinct transcript entries', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'reasoning.delta', chatId: 'c1', reasoning: 'checking facts' }, 'Alpha')

    expect(state.entries).toMatchObject([
      {
        instanceId: 'alpha',
        chatId: 'c1',
        label: 'Alpha',
        role: 'assistant',
        kind: 'reasoning',
        event: 'reasoning.delta',
        text: 'checking facts',
        title: 'Thinking',
      }
    ])
  })

  it('handles deserialized state where streamingKeys is not a Set', () => {
    const state = normalizeTranscriptState({ entries: [], debugEvents: [], nextEntryId: 1, streamingKeys: {} as any } as any)
    expect(state.streamingKeys instanceof Set).toBe(true)

    applyChatEvent(state, { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'works' }, 'Alpha')
    expect(state.entries).toEqual([
      { id: 1, instanceId: 'alpha', chatId: 'c1', label: 'Alpha', role: 'assistant', kind: 'message', event: 'delta', text: 'works', timestamp: expect.any(Number), streamId: 'alpha\0c1\0message', title: undefined, turnId: undefined, status: undefined, name: undefined }
    ])
  })

  it('keeps reasoning and final answer in separate typed streams', () => {
    const state = createTranscriptState()

    applyChatEvent(state, {
      instanceId: 'alpha', event: 'reasoning.delta', chatId: 'c1',
      stream_id: 'turn-1:reasoning', kind: 'reasoning', text: 'I should test this.'
    }, 'Alpha')
    applyChatEvent(state, {
      instanceId: 'alpha', event: 'message.delta', chatId: 'c1',
      stream_id: 'turn-1:message', kind: 'message', text: 'It works.'
    }, 'Alpha')

    expect(state.entries).toMatchObject([
      { kind: 'reasoning', event: 'reasoning.delta', text: 'I should test this.', title: 'Thinking' },
      { kind: 'message', event: 'message.delta', text: 'It works.' }
    ])
  })

  it('appends typed deltas by stream_id and kind', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'message.delta', chatId: 'c1', stream_id: 's1', kind: 'message', text: 'hello ' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'message.delta', chatId: 'c1', stream_id: 's1', kind: 'message', text: 'world' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'message.delta', chatId: 'c1', stream_id: 's2', kind: 'message', text: 'second' }, 'Alpha')

    expect(state.entries.filter((e) => e.role === 'assistant')).toMatchObject([
      { event: 'message.delta', text: 'hello world' },
      { event: 'message.delta', text: 'second' }
    ])
  })

  it('splits inline think blocks from legacy delta streams', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: '<think>I should answer briefly.</think>Hello user.' }, 'Alpha')

    expect(state.entries).toMatchObject([
      { kind: 'reasoning', title: 'Thinking', text: 'I should answer briefly.' },
      { kind: 'message', text: 'Hello user.' }
    ])
  })

  it('handles think tags split across delta chunks', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: '<thi' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'nk>step one</thi' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'nk>final' }, 'Alpha')

    expect(state.entries).toMatchObject([
      { kind: 'reasoning', text: 'step one' },
      { kind: 'message', text: 'final' }
    ])
  })

  it('tracks tool call lifecycle entries', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'tool_call.start', chatId: 'c1', stream_id: 'tool-1', kind: 'tool', name: 'search', detail: 'query docs', status: 'running' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'tool_call.delta', chatId: 'c1', stream_id: 'tool-1', kind: 'tool', detail: 'found result' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'tool_call.end', chatId: 'c1', stream_id: 'tool-1', kind: 'tool', status: 'ok', detail: 'done' }, 'Alpha')

    expect(state.entries).toMatchObject([
      { kind: 'tool', title: 'Tool: search', text: 'query docs\nfound result\ndone', status: 'ok', name: 'search' }
    ])
  })

  it('tracks subagent lifecycle entries', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'subagent.start', chatId: 'c1', stream_id: 'sub-1', kind: 'subagent', subagent_name: 'critic', detail: 'starting', status: 'running' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'subagent.delta', chatId: 'c1', stream_id: 'sub-1', kind: 'subagent', text: 'reviewing' }, 'Alpha')
    applyChatEvent(state, { instanceId: 'alpha', event: 'subagent.end', chatId: 'c1', stream_id: 'sub-1', kind: 'subagent', status: 'ok', detail: 'approved' }, 'Alpha')

    expect(state.entries).toMatchObject([
      { kind: 'subagent', title: 'Sub-agent: critic', text: 'starting\nreviewing\napproved', status: 'ok', name: 'critic' }
    ])
  })

  it('splits think tags from complete message events', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'message', chatId: 'c1', text: '\u003Cthink\u003EI should answer briefly.\u003C/think\u003E\nHello user.' }, 'Alpha')

    expect(state.entries).toMatchObject([
      { kind: 'reasoning', title: 'Thinking', text: 'I should answer briefly.' },
      { kind: 'message', text: '\nHello user.' }
    ])
  })

  it('handles message event without think tags as regular entry', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'message', chatId: 'c1', text: 'Just a normal reply.' }, 'Alpha')

    expect(state.entries).toMatchObject([
      { text: 'Just a normal reply.' }
    ])
  })

  it('handles message event with only think tags (no visible response)', () => {
    const state = createTranscriptState()

    applyChatEvent(state, { instanceId: 'alpha', event: 'message', chatId: 'c1', text: '\u003Cthink\u003EHmm let me think...\u003C/think\u003E' }, 'Alpha')

    expect(state.entries).toMatchObject([
      { kind: 'reasoning', title: 'Thinking', text: 'Hmm let me think...' }
    ])
  })
})
