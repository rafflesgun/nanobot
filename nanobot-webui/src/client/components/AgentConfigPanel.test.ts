import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AgentConfigPanel from './AgentConfigPanel.vue'

vi.mock('./CodeEditor.vue', () => ({
  default: {
    name: 'CodeEditor',
    props: ['modelValue', 'language', 'readOnly', 'placeholder'],
    template: '<div class="code-editor-stub" :data-language="language"><slot /></div>',
    emits: ['update:modelValue']
  }
}))

describe('AgentConfigPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads settings and displays metadata', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
    }))

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Resolved provider'), { timeout: 3000 })
    expect(wrapper.text()).toContain('openai')
  })

  it('shows restart warning when requires_restart is true', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: true })
    }))

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Restart required'), { timeout: 3000 })
  })

  it('blocks save for invalid JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Resolved provider'), { timeout: 3000 })
    const vm = wrapper.vm as any
    vm.jsonDraft = '{bad json'
    await wrapper.get('[data-testid="save-agent-config"]').trigger('click')
    expect(wrapper.text()).toContain('Invalid JSON')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('blocks save when agent.model or agent.provider missing from JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Resolved provider'), { timeout: 3000 })
    const vm = wrapper.vm as any
    vm.jsonDraft = '{"agent": {}}'
    await wrapper.get('[data-testid="save-agent-config"]').trigger('click')
    expect(wrapper.text()).toContain('missing agent model or provider')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('shows no instance message when instance is undefined', () => {
    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: undefined }
    })
    expect(wrapper.text()).toContain('No target instance selected')
  })
})
