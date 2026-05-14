import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AgentConfigPanel from './AgentConfigPanel.vue'

vi.mock('./CodeEditor.vue', () => ({
  default: {
    name: 'CodeEditor',
    props: ['modelValue', 'language', 'readOnly', 'placeholder'],
    template: '<div class="code-editor-stub" :data-language="language" :data-readonly="readOnly"><slot /></div>',
    emits: ['update:modelValue']
  }
}))

describe('AgentConfigPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  const fullConfig = {
    agents: { defaults: { model: 'gpt-4', provider: 'openai' } },
    channels: { websocket: { enabled: true } },
    tools: {},
    gateway: { admin: { enabled: true } }
  }

  it('loads config in read-only mode', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(fullConfig)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.text()).not.toContain('Loading'), { timeout: 3000 })
    expect(wrapper.text()).toContain('read-only')
    expect(wrapper.find('[data-testid="save-agent-config"]').exists()).toBe(false)
    expect(wrapper.find('.btn-primary').text()).toContain('Edit')
  })

  it('enter edit mode, then cancel reverts changes', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(fullConfig)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.text()).not.toContain('Loading'), { timeout: 3000 })

    await wrapper.findAll('.btn-primary').find(b => b.text().includes('Edit'))!.trigger('click')
    expect(wrapper.text()).toContain('editing')
    expect(wrapper.find('[data-testid="save-agent-config"]').exists()).toBe(true)

    const vm = wrapper.vm as any
    const original = vm.jsonDraft
    vm.jsonDraft = '{"modified": true}'
    await wrapper.findAll('.btn-ghost').find(b => b.text().includes('Cancel'))!.trigger('click')

    expect(vm.jsonDraft).toBe(original)
    expect(vm.editing).toBe(false)
  })

  it('blocks save for invalid JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(fullConfig)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.text()).not.toContain('Loading'), { timeout: 3000 })
    await wrapper.findAll('.btn-primary').find(b => b.text().includes('Edit'))!.trigger('click')

    const vm = wrapper.vm as any
    vm.jsonDraft = '{bad json'
    await wrapper.get('[data-testid="save-agent-config"]').trigger('click')
    expect(wrapper.text()).toContain('Invalid JSON')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('blocks save when JSON is not an object', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue(fullConfig)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.text()).not.toContain('Loading'), { timeout: 3000 })
    await wrapper.findAll('.btn-primary').find(b => b.text().includes('Edit'))!.trigger('click')

    const vm = wrapper.vm as any
    vm.jsonDraft = '[1,2,3]'
    await wrapper.get('[data-testid="save-agent-config"]').trigger('click')
    expect(wrapper.text()).toContain('Config must be a JSON object')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('shows no instance message when instance is undefined', () => {
    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: undefined }
    })
    expect(wrapper.text()).toContain('No target instance selected')
  })
})
