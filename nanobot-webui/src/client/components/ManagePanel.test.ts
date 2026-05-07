import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ManagePanel from './ManagePanel.vue'

describe('ManagePanel', () => {
  it('renders target instance selector and management subnav', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue({ logs: [] }) }))
    const wrapper = mount(ManagePanel, {
      props: {
        token: 'dashboard',
        instances: [
          { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true },
          { id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }
        ]
      }
    })

    expect(wrapper.text()).toContain('Target instance')
    expect(wrapper.text()).toContain('Settings')
    expect(wrapper.text()).toContain('Subagents')
    expect(wrapper.text()).toContain('Logs')
    expect(wrapper.text()).toContain('Usage')
    expect(wrapper.text()).toContain('Costing')
    expect(wrapper.text()).toContain('Session')
    expect(wrapper.text()).toContain('Memory')
    expect(wrapper.text()).toContain('Restart')

    await wrapper.get('[data-section="subagents"]').trigger('click')
    expect(wrapper.text()).toContain('Subagents API is not available yet')

    await wrapper.get('[data-section="logs"]').trigger('click')
    expect(wrapper.text()).toContain('Inspect read-only log tails')
  })
})
