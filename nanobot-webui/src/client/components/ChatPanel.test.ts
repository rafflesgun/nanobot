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

describe('ChatPanel', () => {
  it('connects selected instances and broadcasts messages', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://beta', enabled: true }
        ]
      }
    })

    await wrapper.get('input[value="alpha"]').setValue(true)
    await wrapper.get('input[value="beta"]').setValue(true)
    await wrapper.get('[data-testid="connect-group"]').trigger('click')
    await wrapper.get('textarea').setValue('hello group')
    await wrapper.get('form').trigger('submit')

    expect(socket.emitted).toContainEqual({ event: 'connect_group', payload: { instanceIds: ['alpha', 'beta'] } })
    expect(socket.emitted).toContainEqual({ event: 'send_group_message', payload: { text: 'hello group' } })
  })

  it('renders labeled transcript events', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }]
      }
    })

    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'streamed reply' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('alpha')
    expect(wrapper.text()).toContain('streamed reply')
  })

  it('renders markdown code blocks without injecting html', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
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
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
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
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
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
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
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
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
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
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
      }
    })

    socket.emit('chat_event', { instanceId: 'alpha', event: 'chat.connecting', chatId: '' })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('connecting')

    socket.emit('chat_event', { instanceId: 'alpha', event: 'chat.connected', chatId: '' })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('connected')
  })

  it('disables group connect until an enabled instance is selected', async () => {
    const socket = new FakeSocket()
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
      }
    })

    expect(wrapper.get('[data-testid="connect-group"]').attributes('disabled')).toBeDefined()
    await wrapper.get('input[value="alpha"]').setValue(true)
    expect(wrapper.get('[data-testid="connect-group"]').attributes('disabled')).toBeUndefined()
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
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Ops'))
    await wrapper.get('[data-testid="new-topic-name"]').setValue('Support')
    await wrapper.get('[data-testid="create-topic"]').trigger('click')

    expect(loadTopics).toHaveBeenCalledWith('dashboard')
    await vi.waitFor(() => expect(saveTopics).toHaveBeenCalled())
    expect(saveTopics).toHaveBeenLastCalledWith('dashboard', expect.arrayContaining([expect.objectContaining({ id: 'ops', name: 'Ops' }), expect.objectContaining({ name: 'Support' })]))
  })

  it('saves selected instances and transcript updates to persisted topics', async () => {
    const socket = new FakeSocket()
    const saveTopics = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(ChatPanel, {
      props: {
        token: 'dashboard',
        createSocket: () => socket,
        loadTopics: vi.fn().mockResolvedValue([]),
        saveTopics,
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
      }
    })

    await wrapper.get('input[value="alpha"]').setValue(true)
    await wrapper.get('[data-testid="connect-group"]').trigger('click')
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
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Ops'))
    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'legacy topic reply' })
    await wrapper.vm.$nextTick()

    await vi.waitFor(() => expect(saveTopics).toHaveBeenLastCalledWith('dashboard', [expect.objectContaining({
      id: 'ops',
      transcript: expect.objectContaining({ nextEntryId: 2, entries: [expect.objectContaining({ id: 1, text: 'legacy topic reply' })] })
    })]))
  })
})
