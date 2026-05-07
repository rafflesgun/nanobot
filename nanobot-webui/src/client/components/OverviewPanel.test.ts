import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OverviewPanel from './OverviewPanel.vue'

describe('OverviewPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads status cards for enabled instances', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ status: 'ok', model: 'gpt-4.1', provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: ['websocket'], websocket: { enabled: true } })
      })
    )

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('gpt-4.1'))
    expect(wrapper.text()).toContain('openai')
    expect(wrapper.text()).toContain('websocket')
    expect(wrapper.text()).toContain('45s')
  })

  it('shows disabled and failing instances as degraded cards', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, json: vi.fn() }))

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', enabled: false }
        ]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('failed to load status for alpha: 502'))
    expect(wrapper.text()).toContain('beta')
    expect(wrapper.text()).toContain('disabled')
  })
})
