import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import InstancesPanel from './InstancesPanel.vue'

vi.mock('./CodeEditor.vue', () => ({
  default: {
    name: 'CodeEditor',
    props: ['modelValue', 'language', 'readOnly', 'placeholder'],
    template: '<div class="code-editor-stub" :data-language="language"><slot /></div>',
    emits: ['update:modelValue']
  }
}))

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

  it('loads persisted instance drafts and saves CRUD changes', async () => {
    const loadInstances = vi.fn().mockResolvedValue([{ id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }])
    const saveInstances = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(InstancesPanel, {
      props: {
        token: 'dashboard',
        loadInstances,
        saveInstances,
        instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }]
      }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Beta'))
    await wrapper.get('[data-testid="toggle-beta"]').trigger('click')

    expect(loadInstances).toHaveBeenCalledWith('dashboard')
    await vi.waitFor(() => expect(saveInstances).toHaveBeenCalled())
    expect(saveInstances).toHaveBeenLastCalledWith('dashboard', expect.arrayContaining([
      expect.objectContaining({ id: 'alpha', enabled: true }),
      expect.objectContaining({ id: 'beta', enabled: false })
    ]))
  })

  it('toggles between GUI and JSON editor modes', async () => {
    const wrapper = mount(InstancesPanel, {
      props: { instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })
    expect(wrapper.find('.instance-form').exists()).toBe(true)
    expect(wrapper.find('[data-testid="instances-toolbar"]').exists()).toBe(true)

    await wrapper.get('[data-mode="json"]').trigger('click')
    expect(wrapper.find('.instance-form').exists()).toBe(false)
    expect(wrapper.find('[data-testid="instances-json-editor"]').exists()).toBe(true)

    await wrapper.get('[data-mode="gui"]').trigger('click')
    expect(wrapper.find('.instance-form').exists()).toBe(true)
    expect(wrapper.find('[data-testid="instances-json-editor"]').exists()).toBe(false)
  })

  it('serializes instances to JSON when switching to JSON mode', async () => {
    const wrapper = mount(InstancesPanel, {
      props: { instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })
    await wrapper.get('[data-mode="json"]').trigger('click')
    expect((wrapper.vm as any).jsonDraft).toContain('"alpha"')
    expect((wrapper.vm as any).jsonDraft).toContain('"Alpha"')
  })

  it('saves instances from JSON editor', async () => {
    const saveInstances = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(InstancesPanel, {
      props: { token: 'dashboard', saveInstances, instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })
    await wrapper.get('[data-mode="json"]').trigger('click')
    const vm = wrapper.vm as any
    vm.jsonDraft = JSON.stringify([
      { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true },
      { id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true, adminToken: 'tok', websocketToken: 'ws' }
    ])
    await wrapper.get('[data-testid="save-json-instances"]').trigger('click')
    await vi.waitFor(() => expect(saveInstances).toHaveBeenCalled())
    expect(saveInstances).toHaveBeenCalledWith('dashboard', expect.arrayContaining([
      expect.objectContaining({ id: 'beta', name: 'Beta' })
    ]))
  })

  it('blocks save for invalid JSON and shows error', async () => {
    const saveInstances = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(InstancesPanel, {
      props: { token: 'dashboard', saveInstances, instances: [{ id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }] }
    })
    await wrapper.get('[data-mode="json"]').trigger('click')
    const vm = wrapper.vm as any
    vm.jsonDraft = '{bad json'
    await wrapper.get('[data-testid="save-json-instances"]').trigger('click')
    expect(wrapper.text()).toContain('Invalid JSON')
    expect(saveInstances).not.toHaveBeenCalled()
  })

  it('blocks save for valid JSON missing required fields', async () => {
    const saveInstances = vi.fn().mockResolvedValue(undefined)
    const wrapper = mount(InstancesPanel, {
      props: { token: 'dashboard', saveInstances, instances: [] }
    })
    await wrapper.get('[data-mode="json"]').trigger('click')
    const vm = wrapper.vm as any
    vm.jsonDraft = JSON.stringify([{ id: 'alpha' }])
    await wrapper.get('[data-testid="save-json-instances"]').trigger('click')
    expect(wrapper.text()).toContain('missing required field')
    expect(saveInstances).not.toHaveBeenCalled()
  })
})
