import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OverviewPanel from './OverviewPanel.vue'

describe('OverviewPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads status cards for enabled instances', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ status: 'ok', model: 'gpt-4.1', provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: ['websocket'], websocket: { enabled: true } })
    })
    vi.stubGlobal(
      'fetch',
      fetchMock
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
    expect(fetchMock).toHaveBeenCalledOnce()
  })

  it('renders only the latest refresh response', async () => {
    let resolveInitial: (value: unknown) => void = () => {}
    let resolveFirstRefresh: (value: unknown) => void = () => {}
    let resolveSecondRefresh: (value: unknown) => void = () => {}
    const response = (model: string) => ({
      ok: true,
      json: vi.fn().mockResolvedValue({ status: 'ok', model, provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: ['websocket'], websocket: { enabled: true } })
    })
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(new Promise((resolve) => { resolveInitial = resolve }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveFirstRefresh = resolve }))
      .mockReturnValueOnce(new Promise((resolve) => { resolveSecondRefresh = resolve }))

    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    await wrapper.get('button').trigger('click')
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    await wrapper.get('button').trigger('click')
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))

    resolveSecondRefresh(response('latest-model'))
    await vi.waitFor(() => expect(wrapper.text()).toContain('latest-model'))

    resolveInitial(response('initial-model'))
    resolveFirstRefresh(response('stale-model'))

    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(wrapper.text()).toContain('latest-model')
    expect(wrapper.text()).not.toContain('initial-model')
    expect(wrapper.text()).not.toContain('stale-model')
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
