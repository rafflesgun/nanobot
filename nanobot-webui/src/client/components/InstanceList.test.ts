import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import InstanceList from './InstanceList.vue'
import type { PublicInstance } from '../api'

describe('InstanceList', () => {
  it('renders compact instance status without secrets or long detail layout', () => {
    const wrapper = mount(InstanceList, {
      props: {
        instances: [
          { id: 'alpha', name: 'Alpha', baseUrl: 'http://nanobot-alpha:18790', enabled: true, adminToken: 'secret' } as PublicInstance,
          { id: 'beta', name: 'Beta', baseUrl: 'http://nanobot-beta:18790', enabled: false } as PublicInstance
        ]
      }
    })

    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('Beta')
    expect(wrapper.findAll('[data-testid="instance-dot"]')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('secret')
    expect(wrapper.text()).not.toContain('http://nanobot-alpha:18790')
  })
})
