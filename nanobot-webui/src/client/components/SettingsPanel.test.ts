import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SettingsPanel from './SettingsPanel.vue'

describe('SettingsPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads settings and patches model/provider', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ agent: { model: 'old', provider: 'auto', resolved_provider: 'openai', has_api_key: true }, requires_restart: false }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ agent: { model: 'new', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: true }) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(SettingsPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect((wrapper.get('input[name="model"]').element as HTMLInputElement).value).toBe('old'))
    await wrapper.get('input[name="model"]').setValue('new')
    await wrapper.get('input[name="provider"]').setValue('openai')
    await wrapper.get('form').trigger('submit')

    await vi.waitFor(() => expect(wrapper.text()).toContain('Restart required'))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/instances/alpha/settings', expect.objectContaining({ method: 'PATCH' }))
  })

  it('resets save state when a reload supersedes an in-flight save', async () => {
    let resolveSave: (value: unknown) => void = () => {}
    let resolveReload: (value: unknown) => void = () => {}
    const settings = (model: string) => ({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model, provider: 'auto', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
    })
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(settings('old'))
      .mockReturnValueOnce(new Promise((resolve) => { resolveSave = resolve }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveReload = resolve }))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(SettingsPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect((wrapper.get('input[name="model"]').element as HTMLInputElement).value).toBe('old'))
    await wrapper.get('input[name="model"]').setValue('new')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    await wrapper.setProps({ token: 'dashboard-2' })
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))

    resolveReload(settings('reloaded'))
    await vi.waitFor(() => expect((wrapper.get('input[name="model"]').element as HTMLInputElement).value).toBe('reloaded'))
    await vi.waitFor(() => expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined())

    resolveSave(settings('saved'))
    expect((wrapper.get('input[name="model"]').element as HTMLInputElement).value).toBe('reloaded')
  })

  it('switches between GUI, JSON, and Markdown settings editors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
    }))

    const wrapper = mount(SettingsPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect((wrapper.get('input[name="model"]').element as HTMLInputElement).value).toBe('gpt-4'))
    expect(wrapper.text()).toContain('GUI Form')
    expect(wrapper.find('[data-testid="settings-toolbar"]').exists()).toBe(true)

    await wrapper.get('[data-mode="json"]').trigger('click')
    expect((wrapper.get('[data-testid="settings-json"]').element as HTMLTextAreaElement).value).toContain('"model": "gpt-4"')

    await wrapper.get('[data-mode="markdown"]').trigger('click')
    expect(wrapper.get('[data-testid="settings-markdown"]').text()).toContain('Model: `gpt-4`')
    expect(wrapper.get('[data-testid="settings-markdown"]').text()).toContain('Provider: `openai`')

    await wrapper.get('[data-mode="gui"]').trigger('click')
    expect(wrapper.find('input[name="model"]').exists()).toBe(true)
  })

  it('shows invalid JSON errors without saving', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(SettingsPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect((wrapper.get('input[name="model"]').element as HTMLInputElement).value).toBe('gpt-4'))
    await wrapper.get('[data-mode="json"]').trigger('click')
    await wrapper.get('[data-testid="settings-json"]').setValue('{ bad json')
    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('Invalid JSON')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
