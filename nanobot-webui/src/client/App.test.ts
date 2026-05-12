import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App.vue'

describe('App', () => {
  afterEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('shows only the login landing before authentication', () => {
    const wrapper = mount(App)

    expect(wrapper.get('h1').text()).toBe('Nanobot Dashboard')
    expect(wrapper.get('input[type="password"]').attributes('placeholder')).toBe('Dashboard token')
    expect(wrapper.get('button').text()).toBe('Log in')
    expect(wrapper.text()).not.toContain('Agents')
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
    expect(wrapper.text()).not.toContain('Agents')
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
    expect(wrapper.text()).not.toContain('Agents')
    expect(wrapper.text()).not.toContain('http://nanobot-alpha:18790')
  })

  it('shows the approved primary navigation after login', async () => {
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
    expect(wrapper.text()).toContain('Chat')
    expect(wrapper.text()).toContain('Agents')
    expect(wrapper.text()).toContain('Manage Agents')
    expect(wrapper.find('[data-nav="logs"]').exists()).toBe(true)
    expect(wrapper.find('[data-nav="settings"]').exists()).toBe(false)
  })

  it('opens agents and manage sections from the primary navigation', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input)
        if (url === '/api/instances') {
          return Promise.resolve({
            ok: true,
            json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
          })
        }
        return Promise.resolve({
          ok: true,
          json: vi.fn().mockResolvedValue({ agent: { model: 'gpt', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
        })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))

    await wrapper.get('[data-nav="agents"]').trigger('click')
    expect(wrapper.text()).toContain('Local CRUD shell')

    await wrapper.get('[data-nav="manage"]').trigger('click')
    expect(wrapper.text()).toContain('Target instance')
    expect(wrapper.text()).toContain('Subagents')
  })

  it('passes the dashboard token to the persisted instances panel', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/api/instances') {
        return Promise.resolve({
          ok: true,
          json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
        })
      }
      if (url === '/api/state/instances') {
        return Promise.resolve({
          ok: true,
          json: vi.fn().mockResolvedValue({ instances: [{ id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }] })
        })
      }
      throw new Error(`unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))
    await wrapper.get('[data-nav="agents"]').trigger('click')

    await vi.waitFor(() => expect(wrapper.text()).toContain('Beta'))
    expect(fetchMock).toHaveBeenCalledWith('/api/state/instances', { headers: { authorization: 'Bearer secret-token' } })
  })

  it('renders the dark dashboard shell with sidebar and topbar after login', async () => {
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
    expect(wrapper.find('.sidebar').exists()).toBe(true)
    expect(wrapper.find('.topbar').exists()).toBe(true)
    expect(wrapper.find('.content').exists()).toBe(true)
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).not.toContain('http://nanobot-alpha:18790')
  })

  it('toggles sidebar collapse state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="dashboard-shell"]').exists()).toBe(true))

    const collapseButton = wrapper.get('[aria-label="Collapse sidebar"]')
    expect(wrapper.find('.sidebar.is-collapsed').exists()).toBe(false)

    await collapseButton.trigger('click')
    expect(wrapper.find('.sidebar.is-collapsed').exists()).toBe(true)

    await collapseButton.trigger('click')
    expect(wrapper.find('.sidebar.is-collapsed').exists()).toBe(false)
  })

  it('opens and closes mobile drawer at narrow viewport', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App, { attachTo: document.body })
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.find('[data-testid="dashboard-shell"]').exists()).toBe(true))

    expect(document.querySelector('.mobile-drawer')).toBeNull()

    await wrapper.get('[aria-label="Open navigation"]').trigger('click')
    expect(document.querySelector('.mobile-drawer')).not.toBeNull()

    document.querySelector<HTMLElement>('.drawer-backdrop')!.click()
    await wrapper.vm.$nextTick()
    expect(document.querySelector('.mobile-drawer')).toBeNull()

    wrapper.unmount()
  })

  it('shows nav icons after login', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))

    expect(wrapper.find('[data-nav="overview"]').exists()).toBe(true)
    expect(wrapper.find('[data-nav="agents"]').exists()).toBe(true)
    expect(wrapper.find('[data-nav="manage"]').exists()).toBe(true)
    expect(wrapper.find('[data-nav="chat"]').exists()).toBe(true)
  })

  it('switches to Chat tab when Chat nav is clicked', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))

    await wrapper.get('[data-nav="chat"]').trigger('click')
    expect(wrapper.findComponent({ name: 'ChatView' }).exists()).toBe(true)
  })

  it('renders topbar action buttons and status pill', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))

    expect(wrapper.find('[data-testid="refresh-button"]').exists()).toBe(true)
    expect(wrapper.find('.top-actions .pill').exists()).toBe(true)
  })

  it('uses the sticky split-shell layout hooks after login', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')

    await vi.waitFor(() => expect(wrapper.find('.app').exists()).toBe(true))
    expect(wrapper.find('.sidebar').exists()).toBe(true)
    expect(wrapper.find('.brand').exists()).toBe(true)
    expect(wrapper.find('.nav-section').exists()).toBe(true)
    expect(wrapper.find('.topbar').exists()).toBe(true)
    expect(wrapper.find('.crumbs').exists()).toBe(true)
    expect(wrapper.find('.top-actions').exists()).toBe(true)
    expect(wrapper.find('.content').exists()).toBe(true)
  })

  it('shows instance name in breadcrumbs on Manage tab', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))

    await wrapper.get('[data-nav="manage"]').trigger('click')
    const crumbs = wrapper.find('.crumbs')
    expect(crumbs.text()).toContain('Alpha')
  })

  it('shows Logs as a primary nav item and renders LogsPanel when selected', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: vi.fn().mockResolvedValue({ instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] })
      })
    )

    const wrapper = mount(App)
    await wrapper.get('input').setValue('secret-token')
    await wrapper.get('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper.text()).toContain('Overview'))

    expect(wrapper.find('[data-nav="logs"]').exists()).toBe(true)
    await wrapper.get('[data-nav="logs"]').trigger('click')
    expect(wrapper.text()).toContain('Logs')
  })
})
