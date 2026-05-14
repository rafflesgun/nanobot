import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SubagentsPanel from './SubagentsPanel.vue'

vi.mock('./CodeEditor.vue', () => ({
  default: {
    name: 'CodeEditor',
    props: ['modelValue', 'language', 'readOnly', 'placeholder'],
    template: '<textarea class="code-editor-stub" :data-language="language" :readonly="readOnly" @input="$emit(\'update:modelValue\', $event.target.value)" />',
    emits: ['update:modelValue']
  }
}))

describe('SubagentsPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists subagents with description model source and action buttons', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: vi.fn().mockResolvedValue({ subagents: [
      { name: 'recall', description: 'Searches history', model: 'deepseek-v4-flash', source: 'builtin', editable: false },
      { name: 'ops-triage', description: 'Triage incidents', model: 'test/model', source: 'workspace', editable: true }
    ] }) }))
    const wrapper = mount(SubagentsPanel, { props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } } })

    await vi.waitFor(() => expect(wrapper.text()).toContain('ops-triage'))
    expect(wrapper.text()).toContain('Searches history')
    expect(wrapper.text()).toContain('deepseek-v4-flash')
    expect(wrapper.text()).toContain('builtin')
    expect(wrapper.text()).toContain('workspace')
    expect(wrapper.find('[data-testid="delete-recall"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="delete-ops-triage"]').exists()).toBe(true)
  })

  it('opens subagent in read-only mode, then edit and save', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => Promise.resolve({ ok: true, json: vi.fn().mockResolvedValue(init?.method === 'PUT'
      ? { subagent: { name: 'ops-triage', description: 'Updated', model: 'test/model', source: 'workspace', editable: true } }
      : url.endsWith('/ops-triage')
        ? { name: 'ops-triage', description: 'Triage incidents', model: 'test/model', source: 'workspace', editable: true, content: '---\nname: ops-triage\ndescription: Triage incidents\n---\n\nBody' }
        : { subagents: [{ name: 'ops-triage', description: 'Triage incidents', model: 'test/model', source: 'workspace', editable: true }] }) }))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(SubagentsPanel, { props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } } })

    await vi.waitFor(() => expect(wrapper.text()).toContain('ops-triage'))
    await wrapper.get('[data-testid="edit-ops-triage"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('.mode-badge').exists()).toBe(true), { timeout: 3000 })

    expect(wrapper.find('[data-testid="save-subagent"]').exists()).toBe(false)

    const editBtn = wrapper.findAll('.btn-primary').find(b => b.text().includes('Edit'))
    expect(editBtn).toBeTruthy()
    await editBtn!.trigger('click')
    expect(wrapper.find('.mode-badge.editing').exists()).toBe(true)
    expect(wrapper.find('[data-testid="save-subagent"]').exists()).toBe(true)

    await wrapper.get('[data-testid="subagent-markdown"]').setValue('---\nname: ops-triage\ndescription: Updated\n---\n\nUpdated body')
    await wrapper.get('[data-testid="save-subagent"]').trigger('click')

    expect(fetchMock).toHaveBeenCalledWith('/api/instances/alpha/subagents/ops-triage', expect.objectContaining({ method: 'PUT' }))
  })

  it('renders built-in subagents as read-only without edit button', async () => {
    const fetchMock = vi.fn((url: string) => Promise.resolve({ ok: true, json: vi.fn().mockResolvedValue(url.endsWith('/recall')
      ? { name: 'recall', description: 'Searches history', model: 'deepseek', source: 'builtin', editable: false, content: '---\nname: recall\n---\n\nBody' }
      : { subagents: [{ name: 'recall', description: 'Searches history', model: 'deepseek', source: 'builtin', editable: false }] }) }))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(SubagentsPanel, { props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } } })

    await vi.waitFor(() => expect(wrapper.text()).toContain('recall'))
    await wrapper.get('[data-testid="edit-recall"]').trigger('click')

    await vi.waitFor(() => expect(wrapper.find('.mode-badge').exists()).toBe(true), { timeout: 3000 })
    expect(wrapper.findAll('.btn-primary').find(b => b.text().includes('Edit'))).toBeUndefined()
  })

  it('cancel reverts unsaved changes', async () => {
    const fetchMock = vi.fn((url: string) => Promise.resolve({ ok: true, json: vi.fn().mockResolvedValue(url.endsWith('/ops-triage')
      ? { name: 'ops-triage', description: 'Triage', model: 'test/model', source: 'workspace', editable: true, content: 'original content' }
      : { subagents: [{ name: 'ops-triage', description: 'Triage', model: 'test/model', source: 'workspace', editable: true }] }) }))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(SubagentsPanel, { props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } } })

    await vi.waitFor(() => expect(wrapper.text()).toContain('ops-triage'))
    await wrapper.get('[data-testid="edit-ops-triage"]').trigger('click')
    await vi.waitFor(() => expect(wrapper.find('.mode-badge').exists()).toBe(true), { timeout: 3000 })

    const editBtn = wrapper.findAll('.btn-primary').find(b => b.text().includes('Edit'))
    await editBtn!.trigger('click')

    const vm = wrapper.vm as any
    expect(vm.savedMarkdown).toBe('original content')
    vm.markdown = 'modified content'

    const cancelBtn = wrapper.findAll('.btn-ghost').find(b => b.text().includes('Cancel'))
    await cancelBtn!.trigger('click')
    expect(vm.markdown).toBe('original content')
    expect(vm.editing).toBe(false)
  })
})
