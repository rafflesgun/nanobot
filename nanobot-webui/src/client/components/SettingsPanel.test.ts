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
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] }
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
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect((wrapper.get('input[name="model"]').element as HTMLInputElement).value).toBe('old'))
    await wrapper.get('input[name="model"]').setValue('new')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    await wrapper.setProps({ token: 'dashboard-2' })
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))

    resolveReload(settings('reloaded'))
    await vi.waitFor(() => expect((wrapper.get('input[name="model"]').element as HTMLInputElement).value).toBe('reloaded'))
    resolveSave(settings('saved'))

    await vi.waitFor(() => expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined())
    expect((wrapper.get('input[name="model"]').element as HTMLInputElement).value).toBe('reloaded')
  })
})
