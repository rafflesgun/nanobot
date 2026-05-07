import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import LogsPanel from './LogsPanel.vue'

describe('LogsPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads logs and renders selected tail', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ logs: [{ name: 'nanobot.log' }] }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ name: 'nanobot.log', lines: ['line one', 'line two'] }) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(LogsPanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('nanobot.log'))
    await wrapper.get('button[data-log="nanobot.log"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('line two'))
  })
})
