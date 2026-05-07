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

  it('clears log loading state when no instance is selected', async () => {
    const fetchMock = vi.fn().mockReturnValue(new Promise(() => {}))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(LogsPanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Loading logs...'))
    await wrapper.setProps({ instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: false }] })

    await vi.waitFor(() => expect((wrapper.vm as unknown as { loadingLogs: boolean }).loadingLogs).toBe(false))
  })

  it('filters available logs from the toolbar', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ logs: [{ name: 'nanobot.log' }, { name: 'debug.log' }] })
    }))

    const wrapper = mount(LogsPanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('debug.log'))
    expect(wrapper.find('[data-testid="logs-toolbar"]').exists()).toBe(true)

    await wrapper.get('[data-testid="logs-filter"]').setValue('nano')

    expect(wrapper.find('button[data-log="nanobot.log"]').exists()).toBe(true)
    expect(wrapper.find('button[data-log="debug.log"]').exists()).toBe(false)
  })

  it('switches selected log between formatted and raw views', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ logs: [{ name: 'nanobot.log' }] }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ name: 'nanobot.log', lines: ['INFO booted', 'ERROR failed'] }) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(LogsPanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('nanobot.log'))
    await wrapper.get('button[data-log="nanobot.log"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.findAll('[data-testid="formatted-log-line"]')).toHaveLength(2))

    await wrapper.get('[data-view="raw"]').trigger('click')

    expect(wrapper.get('[data-testid="raw-log-tail"]').text()).toContain('INFO booted\nERROR failed')
  })

  it('loads webui runtime logs as a selectable source', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ logs: [] }) })
      .mockResolvedValueOnce({ ok: true, json: vi.fn().mockResolvedValue({ logs: [{ at: '2026-05-07T00:00:00.000Z', level: 'info', method: 'GET', path: '/api/instances', status: 200 }] }) })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(LogsPanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('WebUI Runtime'))
    await wrapper.get('[data-source="webui-runtime"]').trigger('click')

    await vi.waitFor(() => expect(wrapper.text()).toContain('/api/instances'))
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/webui/logs', { headers: { authorization: 'Bearer dashboard' } })
  })
})
