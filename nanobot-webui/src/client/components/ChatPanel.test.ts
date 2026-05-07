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
})
