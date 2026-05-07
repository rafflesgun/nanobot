import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import InstancesPanel from './InstancesPanel.vue'

describe('InstancesPanel', () => {
  it('creates, edits, disables, and deletes local instances without rendering secrets', async () => {
    const wrapper = mount(InstancesPanel, {
      props: {
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
      }
    })

    expect(wrapper.text()).toContain('Alpha')
    await wrapper.get('[data-testid="new-instance-name"]').setValue('Beta')
    await wrapper.get('[data-testid="new-instance-url"]').setValue('http://beta')
    await wrapper.get('[data-testid="new-instance-admin-token"]').setValue('beta-admin-secret')
    await wrapper.get('[data-testid="new-instance-ws-token"]').setValue('beta-ws-secret')
    await wrapper.get('[data-testid="create-instance"]').trigger('click')

    expect(wrapper.text()).toContain('Beta')
    expect(wrapper.text()).not.toContain('beta-admin-secret')
    expect(wrapper.text()).not.toContain('beta-ws-secret')

    await wrapper.get('[data-testid="edit-beta"]').trigger('click')
    await wrapper.get('[data-testid="new-instance-name"]').setValue('Beta Prime')
    await wrapper.get('[data-testid="create-instance"]').trigger('click')
    expect(wrapper.text()).toContain('Beta Prime')

    await wrapper.get('[data-testid="toggle-beta"]').trigger('click')
    expect(wrapper.text()).toContain('disabled')

    await wrapper.get('[data-testid="delete-beta"]').trigger('click')
    expect(wrapper.text()).not.toContain('Beta Prime')
  })
})
