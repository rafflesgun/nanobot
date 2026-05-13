import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ManagePanel from './ManagePanel.vue'

vi.mock('./AgentConfigPanel.vue', () => ({
  default: { name: 'AgentConfigPanel', props: ['token', 'instance'], template: '<div class="agent-config-stub">Agent Config</div>' }
}))
vi.mock('./SubagentsPanel.vue', () => ({
  default: { name: 'SubagentsPanel', props: ['token', 'instance'], template: '<div class="subagents-stub">Subagents</div>' }
}))
vi.mock('./LogsPanel.vue', () => ({
  default: { name: 'LogsPanel', props: ['token', 'instance'], template: '<div class="logs-stub">Logs</div>' }
}))

describe('ManagePanel', () => {
  it('renders instance sidebar with enabled instances only', () => {
    const wrapper = mount(ManagePanel, {
      props: {
        token: 'dashboard',
        instances: [
          { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true },
          { id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true },
          { id: 'gamma', name: 'Gamma', baseUrl: 'http://gamma', enabled: false }
        ]
      }
    })
    expect(wrapper.find('[data-testid="instance-sidebar"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('Beta')
    expect(wrapper.text()).not.toContain('Gamma')
  })

  it('renders sub-nav tabs: Agent Config, Subagents, Logs', () => {
    const wrapper = mount(ManagePanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })
    expect(wrapper.find('[data-section="agent-config"]').exists()).toBe(true)
    expect(wrapper.find('[data-section="subagents"]').exists()).toBe(true)
    expect(wrapper.find('[data-section="logs"]').exists()).toBe(true)
    expect(wrapper.find('[data-section="settings"]').exists()).toBe(false)
    expect(wrapper.find('[data-section="session"]').exists()).toBe(false)
    expect(wrapper.find('[data-section="memory"]').exists()).toBe(false)
    expect(wrapper.find('[data-section="credentials"]').exists()).toBe(false)
  })

  it('renders restart button in header area', () => {
    const wrapper = mount(ManagePanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })
    expect(wrapper.find('[data-testid="restart-button"]').exists()).toBe(true)
  })

  it('clicking instance in sidebar selects it', async () => {
    const wrapper = mount(ManagePanel, {
      props: {
        token: 'dashboard',
        instances: [
          { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true },
          { id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }
        ]
      }
    })
    await wrapper.get('[data-instance="beta"]').trigger('click')
    expect(wrapper.find('[data-instance="beta"]').classes()).toContain('active')
  })

  it('switches between Agent Config and Subagents tabs', async () => {
    const wrapper = mount(ManagePanel, {
      props: { token: 'dashboard', instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })
    expect(wrapper.find('.agent-config-stub').exists()).toBe(true)

    await wrapper.get('[data-section="subagents"]').trigger('click')
    expect(wrapper.find('.subagents-stub').exists()).toBe(true)

    await wrapper.get('[data-section="logs"]').trigger('click')
    expect(wrapper.find('.logs-stub').exists()).toBe(true)
  })
})
