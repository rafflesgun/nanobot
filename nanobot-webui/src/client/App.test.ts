import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'

describe('App', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('keeps dashboard token in memory and shows connect errors', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503, json: vi.fn() })
      .mockResolvedValueOnce({
        ok: true,
        json: vi.fn().mockResolvedValue({
          instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }]
        })
      })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)

    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('button').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('failed to load instances: 503'))

    await wrapper.get('button').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('http://nanobot-alpha:18790'))

    expect(wrapper.text()).not.toContain('failed to load instances: 503')
    expect(setItem).not.toHaveBeenCalledWith('nanobot-webui-token', 'secret-token')
  })
})
