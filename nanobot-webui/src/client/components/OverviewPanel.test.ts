import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import OverviewPanel from './OverviewPanel.vue'

const zeroUsage = { totals: { count: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0, cached_tokens: 0 }, by_day: [], by_model: [], by_channel: [], by_session: [], pricing: { configured: false, message: 'Pricing is not configured; showing token usage only.' } }

function makeFetchMock(statusOverride?: Record<string, unknown>, usageOverride?: Record<string, unknown>) {
  return vi.fn((url: string) => Promise.resolve({
    ok: true,
    json: vi.fn().mockResolvedValue(url.includes('/usage') ? (usageOverride ?? zeroUsage) : url.includes('/webui/logs') ? { logs: [] } : (statusOverride ?? { status: 'ok', model: 'gpt-4.1', provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: ['websocket'], websocket: { enabled: true } }))
  }))
}

describe('OverviewPanel', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders hero section with eyebrow, title, and metrics', async () => {
    vi.stubGlobal('fetch', makeFetchMock())

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('gpt-4.1'))
    expect(wrapper.find('.eyebrow').text()).toBe('Dashboard')
    expect(wrapper.find('#overview-title').text()).toBe('Nanobot Dashboard')
    expect(wrapper.findAll('.metric')).toHaveLength(4)
    expect(wrapper.text()).toContain('instances')
    expect(wrapper.text()).toContain('healthy')
    expect(wrapper.text()).toContain('total tokens')
    expect(wrapper.text()).toContain('degraded')
  })

  it('renders instance table with rows and Model column', async () => {
    vi.stubGlobal('fetch', makeFetchMock())

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', enabled: true }
        ]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('gpt-4.1'))
    expect(wrapper.find('.table-panel').exists()).toBe(true)
    expect(wrapper.find('table').exists()).toBe(true)
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('alpha')
    const headers = wrapper.findAll('th')
    expect(headers.map((h) => h.text())).toContain('Model')
  })

  it('renders live logs panel', async () => {
    vi.stubGlobal('fetch', makeFetchMock())

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('gpt-4.1'))
    expect(wrapper.find('.log-panel').exists()).toBe(true)
    expect(wrapper.text()).toContain('Live logs')
    expect(wrapper.text()).toContain('No recent log entries')
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
    const fetchMock = vi.fn((url: string) => url.includes('/usage') ? Promise.resolve({ ok: true, json: vi.fn().mockResolvedValue(zeroUsage) }) : url.includes('/webui/logs') ? Promise.resolve({ ok: true, json: vi.fn().mockResolvedValue({ logs: [] }) }) : statusResponses.shift())

    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/instances/alpha/status', expect.anything()))
    await wrapper.get('.icon-button-sm').trigger('click')
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
    await wrapper.get('.icon-button-sm').trigger('click')
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

  it('shows disabled and failing instances as degraded with danger dot', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => url.includes('/webui/logs') ? Promise.resolve({ ok: true, json: vi.fn().mockResolvedValue({ logs: [] }) }) : Promise.resolve({ ok: false, status: 502, json: vi.fn() })))

    const wrapper = mount(OverviewPanel, {
      props: {
        token: 'dashboard',
        instances: [
          { id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true },
          { id: 'beta', name: 'beta', baseUrl: 'http://nanobot-beta:18790', enabled: false }
        ]
      }
    })

    await vi.waitFor(() => {
      const rows = wrapper.findAll('tbody tr')
      expect(rows.length).toBeGreaterThanOrEqual(1)
    })
    const rows = wrapper.findAll('tbody tr')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('alpha')
    expect(rows[0].text()).toContain('degraded')
    expect(rows[0].find('.dot.danger').exists()).toBe(true)
    expect(rows[1].text()).toContain('beta')
    expect(rows[1].find('.dot.danger').exists()).toBe(true)
  })

  it('defaults usage selector to the first enabled instance and renders usage cards with chart', async () => {
    const fetchMock = makeFetchMock(undefined, { totals: { count: 2, input_tokens: 30, output_tokens: 12, total_tokens: 42, cached_tokens: 3 }, by_day: [{ key: '2026-05-07', count: 2, input_tokens: 30, output_tokens: 12, total_tokens: 42, cached_tokens: 3 }], by_model: [{ key: 'm1', count: 2, input_tokens: 30, output_tokens: 12, total_tokens: 42, cached_tokens: 3 }], by_channel: [], by_session: [], pricing: { configured: false, message: 'Pricing is not configured; showing token usage only.' } })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(OverviewPanel, {
      props: { token: 'dashboard', instances: [{ id: 'disabled', name: 'Disabled', baseUrl: 'http://disabled', enabled: false }, { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('42'))
    expect((wrapper.get('[data-testid="usage-instance-select"]').element as HTMLSelectElement).value).toBe('alpha')
    expect(wrapper.text()).toContain('Total')
    expect(wrapper.text()).toContain('Pricing is not configured')
    expect(wrapper.find('.usage-chart').exists()).toBe(true)
    expect(wrapper.find('.chart-fill').exists()).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith('/api/instances/alpha/usage?days=30', expect.anything())
  })

  it('renders flat zero usage when no enabled instance exists', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => url.includes('/webui/logs') ? Promise.resolve({ ok: true, json: vi.fn().mockResolvedValue({ logs: [] }) }) : undefined))
    const wrapper = mount(OverviewPanel, { props: { token: 'dashboard', instances: [{ id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: false }] } })

    expect(wrapper.text()).toContain('Total')
    expect(wrapper.text()).toContain('0')
  })

  it('reloads usage when switching usage instance', async () => {
    const alpha = { id: 'alpha', name: 'Alpha', enabled: true }
    const beta = { id: 'beta', name: 'Beta', enabled: true }
    const fetchMock = vi.fn((url: string) => Promise.resolve({
      ok: true,
      json: vi.fn().mockResolvedValue(url.includes('beta/usage')
        ? { totals: { count: 1, input_tokens: 5, output_tokens: 6, total_tokens: 99, cached_tokens: 0 }, by_day: [], by_model: [], by_channel: [], by_session: [], pricing: { configured: false, message: 'Pricing is not configured; showing token usage only.' } }
        : url.includes('/usage') ? zeroUsage : url.includes('/webui/logs') ? { logs: [] } : { status: 'ok', model: 'status-model', provider: 'auto', resolved_provider: 'openai', uptime_s: 45, channels: [], websocket: { enabled: true } })
    }))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(OverviewPanel, { props: { token: 'dashboard', instances: [alpha, beta].map((item) => ({ ...item, baseUrl: `http://${item.id}` })) } })

    await wrapper.get('[data-testid="usage-instance-select"]').setValue('beta')

    await vi.waitFor(() => expect(wrapper.text()).toContain('99'))
    expect(fetchMock).toHaveBeenCalledWith('/api/instances/beta/usage?days=30', expect.anything())
  })
})
