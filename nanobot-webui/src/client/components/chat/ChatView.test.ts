import { mount } from '@vue/test-utils'
import { EventEmitter } from 'node:events'
import { describe, expect, it, vi } from 'vitest'
import ChatView from './ChatView.vue'

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

function mountChatView(socket: FakeSocket, options: Record<string, unknown> = {}) {
  return mount(ChatView, {
    props: {
      token: 'dashboard',
      createSocket: () => socket,
      loadConversationsApi: vi.fn().mockResolvedValue([]),
      saveConversationsApi: vi.fn().mockResolvedValue([]),
      instances: [alpha, beta],
      ...options
    },
    global: {
      stubs: {
        ConversationSidebar: true,
        ChatArea: true,
        NewChatDialog: true,
        AddMemberDialog: true
      }
    }
  })
}

describe('ChatView', () => {
  it('loads conversations on mount', async () => {
    const socket = new FakeSocket()
    const loadApi = vi.fn().mockResolvedValue([])
    mountChatView(socket, { loadConversationsApi: loadApi })
    await vi.waitFor(() => expect(loadApi).toHaveBeenCalledWith('dashboard'))
  })

  it('creates a conversation and ensures connections', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('Code Review', ['alpha'])
    await wrapper.vm.$nextTick()

    const conv = wrapper.vm.conversations[0]
    expect(conv.name).toBe('Code Review')
    expect(conv.selectedIds).toContain('alpha')
    expect(socket.emitted).toContainEqual(
      expect.objectContaining({ event: 'ensure_topic_connections' })
    )
  })

  it('sends a message to the active conversation', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('Chat', ['alpha'])
    await wrapper.vm.$nextTick()

    const conv = wrapper.vm.conversations[0]
    conv.chatMappings = { alpha: { chatId: 'chat-1', status: 'attached' } }
    await wrapper.vm.$nextTick()

    wrapper.vm.sendMessage('hello', [])
    await wrapper.vm.$nextTick()

    expect(socket.emitted).toContainEqual(
      expect.objectContaining({ event: 'send_group_message' })
    )
    const msgEmit = socket.emitted.find(e => e.event === 'send_group_message')
    expect((msgEmit!.payload as any).text).toBe('hello')
  })

  it('canSend is false until chatMappings are attached', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('Chat', ['alpha'])
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.canSend).toBe(false)

    const conv = wrapper.vm.conversations[0]
    conv.chatMappings = { alpha: { chatId: 'chat-1', status: 'attached' } }
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.canSend).toBe(true)
  })

  it('handles delta events as streaming and stops on stream_end', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('Stream', ['alpha'])
    await wrapper.vm.$nextTick()

    const conv = wrapper.vm.conversations[0]
    socket.emit('chat_event', {
      topicId: conv.id,
      instanceId: 'alpha',
      event: 'delta',
      chatId: 'chat-1',
      text: 'hi'
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.isGenerating).toBe(true)

    socket.emit('chat_event', {
      topicId: conv.id,
      instanceId: 'alpha',
      event: 'stream_end',
      chatId: 'chat-1'
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.isGenerating).toBe(false)
  })

  it('clears isGenerating on message event (non-streaming response)', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('NonStream', ['alpha'])
    await wrapper.vm.$nextTick()

    const conv = wrapper.vm.conversations[0]
    conv.chatMappings = { alpha: { chatId: 'chat-1', status: 'attached' } }
    await wrapper.vm.$nextTick()

    wrapper.vm.sendMessage('hello', [])
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.isGenerating).toBe(true)

    socket.emit('chat_event', {
      topicId: conv.id,
      instanceId: 'alpha',
      event: 'message',
      chatId: 'chat-1',
      text: 'response'
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.isGenerating).toBe(false)
  })

  it('accepts delta events for a new turn after stream_end', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('Multi', ['alpha'])
    await wrapper.vm.$nextTick()

    const conv = wrapper.vm.conversations[0]
    socket.emit('chat_event', {
      topicId: conv.id,
      instanceId: 'alpha',
      event: 'delta',
      chatId: 'chat-1',
      text: 'first'
    })
    await wrapper.vm.$nextTick()

    socket.emit('chat_event', {
      topicId: conv.id,
      instanceId: 'alpha',
      event: 'stream_end',
      chatId: 'chat-1'
    })
    await wrapper.vm.$nextTick()

    socket.emit('chat_event', {
      topicId: conv.id,
      instanceId: 'alpha',
      event: 'delta',
      chatId: 'chat-1',
      text: 'second turn'
    })
    await wrapper.vm.$nextTick()

    const entries = conv.transcript.entries as any[]
    const assistantEntries = entries.filter((e: any) => e.role === 'assistant')
    expect(assistantEntries).toHaveLength(2)
    expect(assistantEntries[0].text).toBe('first')
    expect(assistantEntries[1].text).toBe('second turn')
  })

  it('routes attached events to correct conversation chatMappings', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('Attached', ['alpha'])
    await wrapper.vm.$nextTick()

    const conv = wrapper.vm.conversations[0]
    socket.emit('chat_event', {
      topicId: conv.id,
      instanceId: 'alpha',
      event: 'attached',
      chatId: 'chat-1'
    })
    await wrapper.vm.$nextTick()

    expect(conv.chatMappings!.alpha).toBeDefined()
    expect(conv.chatMappings!.alpha.chatId).toBe('chat-1')
    expect(conv.chatMappings!.alpha.status).toBe('attached')
  })

  it('deletes a conversation', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('Delete Me', ['alpha'])
    await wrapper.vm.$nextTick()

    const conv = wrapper.vm.conversations[0]
    wrapper.vm.handleDeleteConversation(conv.id)
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.conversations).toHaveLength(0)
  })

  it('renames a conversation', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('Old Name', ['alpha'])
    await wrapper.vm.$nextTick()

    const conv = wrapper.vm.conversations[0]
    wrapper.vm.handleRenameConversation(conv.id, 'New Name')
    await wrapper.vm.$nextTick()

    expect(conv.name).toBe('New Name')
  })

  it('adds and removes members', async () => {
    const socket = new FakeSocket()
    const wrapper = mountChatView(socket)
    await vi.waitFor(() => expect(wrapper.vm.conversations).toBeDefined())

    wrapper.vm.handleCreateConversation('Members', ['alpha'])
    await wrapper.vm.$nextTick()

    wrapper.vm.addMemberToActive('beta')
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.activeConversation!.selectedIds).toContain('beta')

    wrapper.vm.removeMemberFromActive('beta')
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.activeConversation!.selectedIds).not.toContain('beta')
  })
})
