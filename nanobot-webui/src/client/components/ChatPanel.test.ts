import { mount } from '@vue/test-utils'
import { EventEmitter } from 'node:events'
import { describe, expect, it, vi } from 'vitest'
import ChatPanel from './ChatPanel.vue'

class FakeSocket extends EventEmitter {
  emitted: Array<{ event: string; payload: unknown }> = []
  emit(event: string, payload?: unknown) {
    this.emitted.push({ event, payload })
    return super.emit(event, payload)
  }
  disconnect = vi.fn()
}

const alpha = { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }
const beta = { id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }

describe('ChatPanel', () => {
  it('auto-connects saved enabled topic members and sends typed topic messages', async () => {
    const socket = new FakeSocket()
    const loadTopics = vi.fn().mockResolvedValue([
      {
        id: 'ops',
        name: 'Ops',
        selectedIds: ['alpha', 'beta'],
        chatMappings: {
          alpha: { chatId: 'chat-alpha', status: 'attached' },
          beta: { chatId: 'chat-beta', status: 'attached' }
        },
        transcript: { entries: [], debugEvents: [] }
      }
    ])
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics,
        saveTopics: vi.fn().mockResolvedValue(undefined),
        instances: [alpha, beta]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Ops'))
    await wrapper.get('textarea').setValue('hello group')
    await wrapper.get('form').trigger('submit')

    expect(socket.emitted).toContainEqual({
      event: 'ensure_topic_connections',
      payload: {
        topicId: 'ops',
        members: ['alpha', 'beta'],
        chatMappings: {
          alpha: { chatId: 'chat-alpha', status: 'attached' },
          beta: { chatId: 'chat-beta', status: 'attached' }
        }
      }
    })
    expect(socket.emitted).toContainEqual({
      event: 'send_group_message',
      payload: {
        topicId: 'ops',
        text: 'hello group',
        memberIds: ['alpha', 'beta'],
        chatMappings: {
          alpha: { chatId: 'chat-alpha', status: 'attached' },
          beta: { chatId: 'chat-beta', status: 'attached' }
        }
      }
    })
    expect(wrapper.find('[data-testid="connect-group"]').exists()).toBe(false)
  })

  it('adds a bot as a topic member, persists it, and auto-connects that member', async () => {
    const socket = new FakeSocket()
    const saveTopics = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics: vi.fn().mockResolvedValue([]),
        saveTopics,
        instances: [alpha]
      }
    })

    await wrapper.get('[data-testid="add-member-alpha"]').trigger('click')

    expect(socket.emitted).toContainEqual({ event: 'ensure_topic_connections', payload: { topicId: 'default', members: ['alpha'], chatMappings: {} } })
    await vi.waitFor(() => expect(saveTopics).toHaveBeenLastCalledWith('dashboard', [expect.objectContaining({ selectedIds: ['alpha'] })]))
  })

  it('shows disabled saved members without auto-connecting them', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics: vi.fn().mockResolvedValue([{ id: 'ops', name: 'Ops', selectedIds: ['alpha'], transcript: { entries: [], debugEvents: [] } }]),
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: false }]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Ops'))

    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('disabled')
    expect(socket.emitted.some((event) => event.event === 'ensure_topic_connections')).toBe(false)
  })

  it('sends pending attachments as media and renders attachment chips on the local message', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics: vi.fn().mockResolvedValue([
          { id: 'ops', name: 'Ops', selectedIds: ['alpha'], chatMappings: { alpha: { chatId: 'chat-alpha', status: 'attached' } }, transcript: { entries: [], debugEvents: [] } }
        ]),
        saveTopics: vi.fn().mockResolvedValue(undefined),
        instances: [alpha]
      }
    })
    const file = new File(['notes'], 'notes.txt', { type: 'text/plain' })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Ops'))
    Object.defineProperty(wrapper.get('[data-testid="attachment-input"]').element, 'files', { value: [file] })
    await wrapper.get('[data-testid="attachment-input"]').trigger('change')
    await vi.waitFor(() => expect(wrapper.text()).toContain('notes.txt'))
    await wrapper.get('textarea').setValue('see attachment')
    await wrapper.get('form').trigger('submit')

    await vi.waitFor(() => expect(socket.emitted).toContainEqual({
      event: 'send_group_message',
      payload: {
        topicId: 'ops',
        text: 'see attachment',
        media: [{ name: 'notes.txt', data_url: 'data:text/plain;base64,bm90ZXM=' }],
        memberIds: ['alpha'],
        chatMappings: { alpha: { chatId: 'chat-alpha', status: 'attached' } }
      }
    }))
    expect(wrapper.find('[data-testid="sent-attachment"]').text()).toContain('notes.txt')
  })

  it('copies assistant markdown source without rendered html', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [alpha]
      }
    })

    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: '# Plan\n\nUse `code`.' })
    await wrapper.vm.$nextTick()
    await wrapper.get('[data-testid="copy-markdown"]').trigger('click')

    expect(writeText).toHaveBeenCalledWith('# Plan\n\nUse `code`.')
  })

  it('routes attached events to their topic mappings without switching the active topic', async () => {
    const socket = new FakeSocket()
    const saveTopics = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics: vi.fn().mockResolvedValue([
          { id: 'ops', name: 'Ops', selectedIds: ['alpha'], transcript: { entries: [], debugEvents: [] } },
          { id: 'support', name: 'Support', selectedIds: ['alpha'], transcript: { entries: [], debugEvents: [] } }
        ]),
        saveTopics,
        instances: [alpha]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Ops'))
    await wrapper.get('[data-topic-id="support"]').trigger('click')
    socket.emit('chat_event', { topicId: 'ops', instanceId: 'alpha', event: 'attached', chatId: 'ops-chat' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Support')
    await vi.waitFor(() => expect(saveTopics).toHaveBeenLastCalledWith('dashboard', expect.arrayContaining([
      expect.objectContaining({ id: 'ops', chatMappings: { alpha: { chatId: 'ops-chat', status: 'attached' } } })
    ])))
  })

  it('routes delayed topic replies to the original topic after switching topics', async () => {
    const socket = new FakeSocket()
    const saveTopics = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics: vi.fn().mockResolvedValue([
          { id: 'ops', name: 'Ops', selectedIds: ['alpha'], chatMappings: { alpha: { chatId: 'ops-chat', status: 'attached' } }, transcript: { entries: [], debugEvents: [] } },
          { id: 'support', name: 'Support', selectedIds: [], transcript: { entries: [], debugEvents: [] } }
        ]),
        saveTopics,
        instances: [alpha]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Ops'))
    await wrapper.get('[data-topic-id="support"]').trigger('click')
    socket.emit('chat_event', { topicId: 'ops', instanceId: 'alpha', event: 'delta', chatId: 'ops-chat', text: 'ops delayed reply' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Support')
    expect(wrapper.text()).not.toContain('ops delayed reply')
    await vi.waitFor(() => expect(saveTopics).toHaveBeenLastCalledWith('dashboard', expect.arrayContaining([
      expect.objectContaining({ id: 'ops', transcript: expect.objectContaining({ entries: [expect.objectContaining({ text: 'ops delayed reply' })] }) }),
      expect.objectContaining({ id: 'support', transcript: expect.objectContaining({ entries: [] }) })
    ])))
  })

  it('renders labeled transcript events', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [alpha]
      }
    })

    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'streamed reply' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('streamed reply')
  })

  it('renders markdown code blocks without injecting html', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [alpha]
      }
    })

    socket.emit('chat_event', {
      instanceId: 'alpha',
      event: 'delta',
      chatId: 'c1',
      text: '# Plan\n\n```ts\nconst tag = `<script>`\n```'
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('.markdown-heading').text()).toBe('Plan')
    expect(wrapper.get('code[data-language="ts"]').text()).toBe('const tag = `<script>`')
    expect(wrapper.find('script').exists()).toBe(false)
  })

  it('renders tool and reasoning events as distinct transcript blocks', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [alpha]
      }
    })

    socket.emit('chat_event', { instanceId: 'alpha', event: 'tool_call.created', chatId: 'c1', tool: 'shell', detail: 'npm test' })
    socket.emit('chat_event', { instanceId: 'alpha', event: 'reasoning.delta', chatId: 'c1', reasoning: 'checking output' })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('.transcript-entry.is-tool').text()).toContain('Tool: shell')
    expect(wrapper.get('.transcript-entry.is-tool').text()).toContain('npm test')
    expect(wrapper.get('.transcript-entry.is-reasoning').text()).toContain('Reasoning')
    expect(wrapper.get('.transcript-entry.is-reasoning').text()).toContain('checking output')
  })

  it('merges delta chunks and hides terminal events from the visible transcript', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [alpha]
      }
    })

    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'hello ' })
    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'world' })
    socket.emit('chat_event', { instanceId: 'alpha', event: 'stream_end', chatId: 'c1' })
    socket.emit('chat_event', { instanceId: 'alpha', event: 'turn_end', chatId: 'c1' })
    await wrapper.vm.$nextTick()

    expect(wrapper.findAll('.transcript-entry')).toHaveLength(1)
    expect(wrapper.text()).toContain('hello world')
    const visibleTranscript = wrapper.findAll('.transcript-entry').map((entry) => entry.text()).join(' ')
    expect(visibleTranscript).not.toContain('stream_end')
    expect(visibleTranscript).not.toContain('turn_end')
  })

  it('keeps raw protocol events in a debug drawer', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [alpha]
      }
    })

    socket.emit('chat_event', { instanceId: 'alpha', event: 'stream_end', chatId: 'c1' })
    await wrapper.vm.$nextTick()

    expect(wrapper.get('summary').text()).toContain('Debug events')
    expect(wrapper.get('details').text()).toContain('stream_end')
  })

  it('creates and switches local chat topics', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [alpha]
      }
    })

    await wrapper.get('[data-testid="new-topic-name"]').setValue('Ops')
    await wrapper.get('[data-testid="create-topic"]').trigger('click')
    expect(wrapper.text()).toContain('Ops')
    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'ops', text: 'ops reply' })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('ops reply')

    await wrapper.get('[data-topic-id="default"]').trigger('click')
    expect(wrapper.text()).not.toContain('ops reply')
  })

  it('renders per-instance connection status events', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [alpha]
      }
    })

    await wrapper.get('[data-testid="add-member-alpha"]').trigger('click')
    socket.emit('chat_event', { instanceId: 'alpha', event: 'chat.connecting', chatId: '' })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('connecting')

    socket.emit('chat_event', { instanceId: 'alpha', event: 'chat.connected', chatId: '' })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('connected')
  })

  it('loads persisted topics and saves topic changes', async () => {
    const socket = new FakeSocket()
    const loadTopics = vi.fn().mockResolvedValue([{ id: 'ops', name: 'Ops', selectedIds: ['alpha'], transcript: { entries: [], debugEvents: [] } }])
    const saveTopics = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics,
        saveTopics,
        instances: [alpha]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Ops'))
    await wrapper.get('[data-testid="new-topic-name"]').setValue('Support')
    await wrapper.get('[data-testid="create-topic"]').trigger('click')

    expect(loadTopics).toHaveBeenCalledWith('dashboard')
    await vi.waitFor(() => expect(saveTopics).toHaveBeenCalled())
    expect(saveTopics).toHaveBeenLastCalledWith('dashboard', expect.arrayContaining([expect.objectContaining({ id: 'ops', name: 'Ops' }), expect.objectContaining({ name: 'Support' })]))
  })

  it('saves selected members and transcript updates to persisted topics', async () => {
    const socket = new FakeSocket()
    const saveTopics = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics: vi.fn().mockResolvedValue([]),
        saveTopics,
        instances: [alpha]
      }
    })

    await wrapper.get('[data-testid="add-member-alpha"]').trigger('click')
    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'persist me' })
    await wrapper.vm.$nextTick()

    await vi.waitFor(() => expect(saveTopics).toHaveBeenCalledWith('dashboard', [expect.objectContaining({
      id: 'default',
      selectedIds: ['alpha'],
      transcript: expect.objectContaining({ entries: [expect.objectContaining({ text: 'persist me' })] })
    })]))
  })

  it('normalizes legacy persisted topics before appending transcript entries', async () => {
    const socket = new FakeSocket()
    const saveTopics = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics: vi.fn().mockResolvedValue([{ id: 'ops', name: 'Ops', selectedIds: ['alpha'], transcript: { entries: [], debugEvents: [] } }]),
        saveTopics,
        instances: [alpha]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Ops'))
    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'legacy topic reply' })
    await wrapper.vm.$nextTick()

    await vi.waitFor(() => expect(saveTopics).toHaveBeenLastCalledWith('dashboard', [expect.objectContaining({
      id: 'ops',
      chatMappings: {},
      transcript: expect.objectContaining({ nextEntryId: 2, entries: [expect.objectContaining({ id: 1, text: 'legacy topic reply' })] })
    })]))
  })
})
