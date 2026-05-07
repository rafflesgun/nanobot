import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OverviewPanel from './OverviewPanel.vue'

const zeroUsage = { totals: { count: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0, cached_tokens: 0 }, by_day: [], by_model: [], by_channel: [], by_session: [], pricing: { configured: false, message: 'Pricing is not configured; showing token usage only.' } }

describe('OverviewPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('loads status cards for enabled instances', async () => {
    const fetchMock = vi.fn((url: string) => Promise.resolve({
      ok: true,
      json: vi.fn().mockResolvedValue(url.includes('/usage') ? zeroUsage : { status: 'ok', model: 'gpt-4.1', provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: ['websocket'], websocket: { enabled: true } })
    }))
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
    expect(fetchMock).toHaveBeenCalledWith('/api/instances/alpha/status', expect.anything())
  })

  it('renders only the latest refresh response', async () => {
    let resolveInitial: (value: unknown) => void = () => {}
    let resolveFirstRefresh: (value: unknown) => void = () => {}
    let resolveSecondRefresh: (value: unknown) => void = () => {}
    const response = (model: string) => ({
      ok: true,
      json: vi.fn().mockResolvedValue({ status: 'ok', model, provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: ['websocket'], websocket: { enabled: true } })
    })
    const statusResponses = [
      new Promise((resolve) => { resolveInitial = resolve }),
      new Promise((resolve) => { resolveFirstRefresh = resolve }),
      new Promise((resolve) => { resolveSecondRefresh = resolve })
    ]
    const fetchMock = vi.fn((url: string) => url.includes('/usage') ? Promise.resolve({ ok: true, json: vi.fn().mockResolvedValue(zeroUsage) }) : statusResponses.shift())

    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/instances/alpha/status', expect.anything()))
    await wrapper.get('button').trigger('click')
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    await wrapper.get('button').trigger('click')
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))

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

  it('defaults usage selector to the first enabled instance and renders usage cards', async () => {
    const fetchMock = vi.fn((url: string) => Promise.resolve({
      ok: true,
      json: vi.fn().mockResolvedValue(url.includes('/usage')
        ? { totals: { count: 2, input_tokens: 30, output_tokens: 12, total_tokens: 42, cached_tokens: 3 }, by_day: [{ key: '2026-05-07', count: 2, input_tokens: 30, output_tokens: 12, total_tokens: 42, cached_tokens: 3 }], by_model: [{ key: 'm1', count: 2, input_tokens: 30, output_tokens: 12, total_tokens: 42, cached_tokens: 3 }], by_channel: [], by_session: [], pricing: { configured: false, message: 'Pricing is not configured; showing token usage only.' } }
        : { status: 'ok', model: 'gpt-4.1', provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: ['websocket'], websocket: { enabled: true } })
    }))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(OverviewPanel, {
      props: { token: 'dashboard', instances: [{ id: 'disabled', name: 'Disabled', baseUrl: 'http://disabled', enabled: false }, { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('42'))
    expect((wrapper.get('[data-testid="usage-instance-select"]').element as HTMLSelectElement).value).toBe('alpha')
    expect(wrapper.text()).toContain('Total tokens')
    expect(wrapper.text()).toContain('Pricing is not configured')
    expect(fetchMock).toHaveBeenCalledWith('/api/instances/alpha/usage?days=30', expect.anything())
  })

  it('renders flat zero usage when no enabled instance exists', async () => {
    vi.stubGlobal('fetch', vi.fn())
    const wrapper = mount(OverviewPanel, { props: { token: 'dashboard', instances: [{ id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: false }] } })

    expect(wrapper.text()).toContain('No enabled instance selected')
    expect(wrapper.text()).toContain('Total tokens')
    expect(wrapper.text()).toContain('0')
  })

  it('reloads usage when switching usage instance', async () => {
    const alpha = { id: 'alpha', name: 'Alpha', enabled: true }
    const beta = { id: 'beta', name: 'Beta', enabled: true }
    const fetchMock = vi.fn((url: string) => Promise.resolve({
      ok: true,
      json: vi.fn().mockResolvedValue(url.includes('beta/usage')
        ? { totals: { count: 1, input_tokens: 5, output_tokens: 6, total_tokens: 11, cached_tokens: 0 }, by_day: [], by_model: [{ key: 'beta-model', count: 1, input_tokens: 5, output_tokens: 6, total_tokens: 11, cached_tokens: 0 }], by_channel: [], by_session: [], pricing: { configured: false, message: 'Pricing is not configured; showing token usage only.' } }
        : { status: 'ok', model: 'status-model', provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: [], websocket: { enabled: true } })
    }))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(OverviewPanel, { props: { token: 'dashboard', instances: [alpha, beta].map((item) => ({ ...item, baseUrl: `http://${item.id}` })) } })

    await wrapper.get('[data-testid="usage-instance-select"]').setValue('beta')

    await vi.waitFor(() => expect(wrapper.text()).toContain('beta-model'))
  })
})
