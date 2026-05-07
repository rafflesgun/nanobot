import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'

describe('App', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('shows only the login landing before authentication', () => {
    const wrapper = mount(App)

    expect(wrapper.get('h1').text()).toBe('Nanobot Web UI')
    expect(wrapper.get('input[type="password"]').attributes('placeholder')).toBe('Dashboard token')
    expect(wrapper.get('button').text()).toBe('Log in')
    expect(wrapper.text()).not.toContain('Instances')
    expect(wrapper.text()).not.toContain('Chat')
    expect(wrapper.text()).not.toContain('http://nanobot-alpha:18790')
  })

  it('keeps dashboard token in memory, gates dashboard details, and shows login errors', async () => {
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
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('failed to load instances: 503'))
    expect(wrapper.text()).not.toContain('Instances')
    expect(wrapper.text()).not.toContain('Chat')

    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))
    expect(wrapper.text()).toContain('Chat')
    expect(wrapper.text()).toContain('alpha')
    expect(wrapper.text()).not.toContain('http://nanobot-alpha:18790')

    expect(wrapper.text()).not.toContain('failed to load instances: 503')
    expect(setItem).not.toHaveBeenCalledWith('nanobot-webui-token', 'secret-token')
  })

  it('logs out back to the login landing without dashboard details', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({
          instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }]
        })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('alpha'))
    expect(wrapper.text()).not.toContain('http://nanobot-alpha:18790')

    await wrapper.get('[data-testid="logout-button"]').trigger('click')

    expect(wrapper.get('button').text()).toBe('Log in')
    expect(wrapper.text()).not.toContain('Instances')
    expect(wrapper.text()).not.toContain('http://nanobot-alpha:18790')
  })

  it('shows dashboard tabs after login', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')

    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))
    expect(wrapper.text()).toContain('Group Chat')
    expect(wrapper.text()).toContain('Logs')
    expect(wrapper.text()).toContain('Settings')
  })

  it('renders the dark dashboard shell without full instance details after login', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')

    await vi.waitFor(() => expect(wrapper.find('[data-testid="dashboard-shell"]').exists()).toBe(true))
    expect(wrapper.find('[data-testid="sidebar-nav"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="instance-status-bar"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).not.toContain('http://nanobot-alpha:18790')
  })
})
