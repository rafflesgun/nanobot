import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ManagePanel from './ManagePanel.vue'

describe('ManagePanel', () => {
  it('renders target instance selector and management subnav', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => Promise.resolve({ ok: true, json: vi.fn().mockResolvedValue(url.includes('/subagents') ? { subagents: [{ name: 'ops-triage', description: 'Triage incidents', model: 'test/model', source: 'workspace', editable: true }] } : { logs: [] }) })))
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
    expect(wrapper.text()).not.toContain('Usage')
    expect(wrapper.text()).not.toContain('Costing')
    expect(wrapper.text()).toContain('Session')
    expect(wrapper.text()).toContain('Memory')
    expect(wrapper.text()).toContain('Restart')

    await wrapper.get('[data-section="subagents"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.text()).toContain('ops-triage'))

    await wrapper.get('[data-section="logs"]').trigger('click')
    expect(wrapper.text()).toContain('Inspect read-only log tails')
  })

  it('renders credentials section in manage subnav', async () => {
    const wrapper = mount(ManagePanel, {
      props: { token: 'tok', instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })
    expect(wrapper.find('[data-section="credentials"]').exists()).toBe(true)
  })
})
