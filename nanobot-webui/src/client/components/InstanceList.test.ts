import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import InstanceList from './InstanceList.vue'
import type { PublicInstance } from '../api'

describe('InstanceList', () => {
  it('renders instances without tokens', () => {
    const wrapper = mount(InstanceList, {
      props: {
        instances: [
          {
            id: 'alpha',
            name: 'alpha',
            baseUrl: 'http://nanobot-alpha:18790',
            enabled: true,
            adminToken: 'secret'
          } as PublicInstance
        ]
      }
    })

    expect(wrapper.text()).toContain('alpha')
    expect(wrapper.text()).toContain('http://nanobot-alpha:18790')
    expect(wrapper.text()).not.toContain('secret')
  })
})
