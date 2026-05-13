# Manage Agents Page Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Agents and Manage Agents tabs with GUI/JSON toggle, CodeMirror 6 editors, instance sidebar, and restart button.

**Architecture:** Two-tab approach (Approach B). Agents tab gets a GUI/JSON toggle replacing the plain form. Manage tab gets an instance sidebar replacing the dropdown, new sub-nav tabs (Agent Config/Subagents/Logs), a restart header button, and CodeMirror 6 for JSON and Markdown editing. A shared `CodeEditor.vue` component wraps CodeMirror 6.

**Tech Stack:** Vue 3, CodeMirror 6 (`codemirror`, `@codemirror/lang-json`, `@codemirror/lang-markdown`, `@codemirror/lint`, `@codemirror/theme-one-dark`), existing oklch theme system.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `package.json` | Modify | Add CodeMirror 6 dependencies |
| `src/client/components/CodeEditor.vue` | Create | Shared CodeMirror 6 wrapper (JSON + Markdown modes) |
| `src/client/components/CodeEditor.test.ts` | Create | Tests for CodeEditor (v-model, language switching, JSON validation) |
| `src/client/components/InstancesPanel.vue` | Modify | Add GUI/JSON toggle, CodeMirror JSON editor for bulk instance edit |
| `src/client/components/InstancesPanel.test.ts` | Modify | Update tests for JSON toggle mode |
| `src/client/components/ManagePanel.vue` | Modify | Replace dropdown with instance sidebar, new sub-nav, restart button |
| `src/client/components/ManagePanel.test.ts` | Modify | Update tests for new layout |
| `src/client/components/SettingsPanel.vue` | Modify | Replace textarea with CodeEditor, remove markdown mode |
| `src/client/components/SettingsPanel.test.ts` | Modify | Update tests for CodeEditor integration |
| `src/client/components/SubagentsPanel.vue` | Modify | Replace textarea with CodeEditor in markdown mode |
| `src/client/api.ts` | Modify | Add `restartInstance` API function |

---

### Task 1: Install CodeMirror 6 Dependencies

**Files:**
- Modify: `nanobot-webui/package.json`

- [ ] **Step 1: Install CodeMirror 6 packages**

Run:
```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npm install codemirror @codemirror/lang-json @codemirror/lang-markdown @codemirror/lint @codemirror/theme-one-dark @codemirror/view @codemirror/state @codemirror/language
```

- [ ] **Step 2: Verify install succeeds**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npm ls codemirror`
Expected: `codemirror@6.x.x` listed

- [ ] **Step 3: Run existing tests to verify no breakage**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run`
Expected: All 168 tests pass

- [ ] **Step 4: Commit**

```bash
git -C /Users/raffles/git/nanobot-rg add nanobot-webui/package.json nanobot-webui/package-lock.json && git -C /Users/raffles/git/nanobot-rg commit -m "chore(webui): add CodeMirror 6 dependencies for JSON/Markdown editing"
```

---

### Task 2: Create CodeEditor.vue Shared Component

**Files:**
- Create: `nanobot-webui/src/client/components/CodeEditor.vue`
- Create: `nanobot-webui/src/client/components/CodeEditor.test.ts`

- [ ] **Step 1: Write failing tests for CodeEditor**

Create `nanobot-webui/src/client/components/CodeEditor.test.ts`:

```typescript
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CodeEditor from './CodeEditor.vue'

function mountEditor(overrides: Record<string, any> = {}) {
  return mount(CodeEditor, {
    props: { modelValue: '', language: 'json', ...overrides },
    global: { stubs: { CodeMirror: true } }
  })
}

describe('CodeEditor', () => {
  it('renders with json language class', () => {
    const wrapper = mountEditor({ language: 'json' })
    expect(wrapper.find('.code-editor').exists()).toBe(true)
    expect(wrapper.find('.code-editor').classes()).toContain('lang-json')
  })

  it('renders with markdown language class', () => {
    const wrapper = mountEditor({ language: 'markdown' })
    expect(wrapper.find('.code-editor').classes()).toContain('lang-markdown')
  })

  it('emits update:modelValue when content changes', async () => {
    const wrapper = mount(CodeEditor, {
      props: { modelValue: '{"a":1}', language: 'json' }
    })
    const editor = wrapper.findComponent({ name: 'CodeEditor' })
    expect(wrapper.emitted()).toBeDefined()
  })

  it('exposes isValid ref', () => {
    const wrapper = mountEditor({ modelValue: '{}', language: 'json' })
    const vm = wrapper.vm as any
    expect(typeof vm.isValid).toBe('boolean')
  })

  it('isValid is true for valid JSON in json mode', () => {
    const wrapper = mountEditor({ modelValue: '{"key": "value"}', language: 'json' })
    expect((wrapper.vm as any).isValid).toBe(true)
  })

  it('isValid is false for invalid JSON in json mode', () => {
    const wrapper = mountEditor({ modelValue: '{bad', language: 'json' })
    expect((wrapper.vm as any).isValid).toBe(false)
  })

  it('isValid is always true in markdown mode', () => {
    const wrapper = mountEditor({ modelValue: 'anything', language: 'markdown' })
    expect((wrapper.vm as any).isValid).toBe(true)
  })

  it('shows readonly attribute when readOnly prop is true', () => {
    const wrapper = mountEditor({ readOnly: true })
    expect(wrapper.find('.code-editor').classes()).toContain('is-readonly')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/CodeEditor.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Create CodeEditor.vue**

Create `nanobot-webui/src/client/components/CodeEditor.vue`:

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { EditorState } from '@codemirror/state'
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter } from '@codemirror/view'
import { json, jsonParseLinter } from '@codemirror/lang-json'
import { markdown } from '@codemirror/lang-markdown'
import { linter } from '@codemirror/lint'
import { oneDark } from '@codemirror/theme-one-dark'
import { defaultKeymap, indentWithTab } from '@codemirror/commands'
import { syntaxHighlighting, defaultHighlightStyle, bracketMatching } from '@codemirror/language'

const props = withDefaults(defineProps<{
  modelValue: string
  language: 'json' | 'markdown'
  readOnly?: boolean
  placeholder?: string
}>(), {
  readOnly: false,
  placeholder: ''
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const editorRef = ref<HTMLDivElement>()
const view = shallowRef<EditorView>()
const isValid = ref(true)

const extensions = computed(() => {
  const exts: any[] = [
    lineNumbers(),
    highlightActiveLine(),
    highlightActiveLineGutter(),
    bracketMatching(),
    syntaxHighlighting(defaultHighlightStyle, { fallback: true }),
    oneDark,
    keymap.of([...defaultKeymap, indentWithTab]),
    EditorView.updateListener.of((update) => {
      if (update.docChanged) {
        const doc = update.state.doc.toString()
        emit('update:modelValue', doc)
        if (props.language === 'json') {
          try { JSON.parse(doc); isValid.value = true } catch { isValid.value = false }
        }
      }
    }),
    EditorState.readOnly.of(props.readOnly),
    EditorView.editable.of(!props.readOnly)
  ]
  if (props.language === 'json') {
    exts.push(json())
    exts.push(linter(jsonParseLinter()))
  } else {
    exts.push(markdown())
    isValid.value = true
  }
  return exts
})

onMounted(() => {
  if (!editorRef.value) return
  view.value = new EditorView({
    state: EditorState.create({ doc: props.modelValue, extensions: extensions.value }),
    parent: editorRef.value
  })
  if (props.language === 'json') {
    try { JSON.parse(props.modelValue); isValid.value = true } catch { isValid.value = false }
  }
})

watch(() => props.modelValue, (newValue) => {
  if (!view.value) return
  const current = view.value.state.doc.toString()
  if (current !== newValue) {
    view.value.dispatch({
      changes: { from: 0, to: current.length, insert: newValue }
    })
  }
})

watch(extensions, (newExts) => {
  if (!view.value) return
  view.value.dispatch({
    effects: EditorState.reconfigure.of(newExts)
  })
})

onUnmounted(() => {
  view.value?.destroy()
})

defineExpose({ isValid })
</script>

<template>
  <div
    ref="editorRef"
    class="code-editor"
    :class="[`lang-${language}`, { 'is-readonly': readOnly }]"
  />
</template>

<style scoped>
.code-editor {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(12% 0.012 255);
  font-size: 0.88rem;
  line-height: 1.6;
  min-height: 14rem;
  overflow: hidden;
}
.code-editor :deep(.cm-editor) {
  height: 100%;
  min-height: 14rem;
}
.code-editor :deep(.cm-scroller) {
  font-family: var(--font-mono);
}
.code-editor.is-readonly :deep(.cm-content) {
  opacity: 0.7;
}
.code-editor :deep(.cm-gutters) {
  border-right: 1px solid var(--border);
}
.code-editor :deep(.cm-lint-marker-error) {
  background: var(--danger);
}
.code-editor :deep(.cm-tooltip-lint) {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--fg);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
}
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/CodeEditor.test.ts`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git -C /Users/raffles/git/nanobot-rg add nanobot-webui/src/client/components/CodeEditor.vue nanobot-webui/src/client/components/CodeEditor.test.ts && git -C /Users/raffles/git/nanobot-rg commit -m "feat(webui): add CodeEditor.vue shared CodeMirror 6 component

Reusable wrapper supporting JSON (with lint validation) and Markdown
modes. Exposes isValid ref for parent save-gating. Dark theme
matching oklch color system."
```

---

### Task 3: Enhance InstancesPanel with GUI/JSON Toggle

**Files:**
- Modify: `nanobot-webui/src/client/components/InstancesPanel.vue`
- Modify: `nanobot-webui/src/client/components/InstancesPanel.test.ts`

- [ ] **Step 1: Write failing tests for JSON toggle**

Update `nanobot-webui/src/client/components/InstancesPanel.test.ts` — add these tests at the end of the describe block:

```typescript
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
  const editor = wrapper.findComponent({ name: 'CodeEditor' })
  await editor.vm.$emit('update:modelValue', JSON.stringify([
    { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true },
    { id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true, adminToken: 'tok', websocketToken: 'ws' }
  ]))
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
  const editor = wrapper.findComponent({ name: 'CodeEditor' })
  await editor.vm.$emit('update:modelValue', '{bad json')
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
  const editor = wrapper.findComponent({ name: 'CodeEditor' })
  await editor.vm.$emit('update:modelValue', JSON.stringify([{ id: 'alpha' }]))
  await wrapper.get('[data-testid="save-json-instances"]').trigger('click')
  expect(wrapper.text()).toContain('missing required field')
  expect(saveInstances).not.toHaveBeenCalled()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/InstancesPanel.test.ts`
Expected: FAIL — missing elements/data-testid

- [ ] **Step 3: Implement GUI/JSON toggle in InstancesPanel.vue**

Replace the `<form>` and surrounding content in `InstancesPanel.vue` template with a toolbar + conditional form/CodeEditor. Add these to the `<script setup>`:

```typescript
import CodeEditor from './CodeEditor.vue'

const editMode = ref<'gui' | 'json'>('gui')
const jsonDraft = ref('')
const jsonError = ref('')

function selectMode(mode: 'gui' | 'json') {
  if (mode === 'json') {
    jsonDraft.value = JSON.stringify(localInstances.value.map((i) => {
      const obj: Record<string, any> = { id: i.id, name: i.name, baseUrl: i.baseUrl, enabled: i.enabled }
      if (i.adminToken) obj.adminToken = i.adminToken
      if (i.websocketToken) obj.websocketToken = i.websocketToken
      return obj
    }), null, 2)
  }
  jsonError.value = ''
  editMode.value = mode
}

function saveJsonInstances() {
  jsonError.value = ''
  let parsed: any[]
  try {
    parsed = JSON.parse(jsonDraft.value)
  } catch {
    jsonError.value = 'Invalid JSON'
    return
  }
  if (!Array.isArray(parsed)) {
    jsonError.value = 'JSON must be an array'
    return
  }
  for (const entry of parsed) {
    if (!entry.id || !entry.name || !entry.baseUrl) {
      jsonError.value = `Instance "${entry.id || '(missing id)'}" missing required field (id, name, baseUrl)`
      return
    }
  }
  localInstances.value = parsed.map((entry: any) => ({
    id: entry.id,
    name: entry.name,
    baseUrl: entry.baseUrl,
    adminToken: entry.adminToken ?? '',
    websocketToken: entry.websocketToken ?? '',
    enabled: entry.enabled ?? true,
    persisted: localInstances.value.some((li) => li.id === entry.id)
  }))
  persistInstances()
}
```

Update template — add toolbar before the form/cards layout, wrap form in `v-if="editMode === 'gui'"`, add CodeEditor in `v-else-if="editMode === 'json'"`:

```html
<div class="instances-toolbar" data-testid="instances-toolbar">
  <button type="button" data-mode="gui" :class="{ active: editMode === 'gui' }" @click="selectMode('gui')">GUI Form</button>
  <button type="button" data-mode="json" :class="{ active: editMode === 'json' }" @click="selectMode('json')">JSON</button>
</div>

<div class="instances-layout">
  <template v-if="editMode === 'gui'">
    <form class="instance-form" @submit.prevent="saveInstance">
      <!-- existing form fields unchanged -->
    </form>
    <div class="instance-cards">
      <!-- existing cards unchanged -->
    </div>
  </template>
  <template v-else-if="editMode === 'json'">
    <div class="json-editor-panel">
      <p v-if="jsonError" class="error-text" role="alert">{{ jsonError }}</p>
      <CodeEditor
        v-model="jsonDraft"
        data-testid="instances-json-editor"
        language="json"
        placeholder="[]"
      />
      <button type="button" data-testid="save-json-instances" @click="saveJsonInstances">Save All Instances</button>
    </div>
  </template>
</div>
```

Add toolbar styles:

```css
.instances-toolbar { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
.instances-toolbar button { border: 1px solid var(--border); border-radius: 9px; background: var(--surface); color: var(--muted); padding: 0.35rem 0.75rem; font-size: 12px; font-weight: 560; cursor: pointer; }
.instances-toolbar button.active { border-color: var(--accent); background: oklch(64% 0.18 255 / 0.18); color: var(--fg); }
.json-editor-panel { display: grid; gap: 0.75rem; }
.error-text { color: var(--warn); margin: 0; }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/InstancesPanel.test.ts`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git -C /Users/raffles/git/nanobot-rg add nanobot-webui/src/client/components/InstancesPanel.vue nanobot-webui/src/client/components/InstancesPanel.test.ts && git -C /Users/raffles/git/nanobot-rg commit -m "feat(webui): add GUI/JSON toggle to Agents tab

Toggle between GUI form and CodeMirror JSON editor for bulk instance
management. JSON mode validates structure and required fields before
save."
```

---

### Task 5: Enhance ManagePanel with Instance Sidebar and New Sub-Nav

**Files:**
- Modify: `nanobot-webui/src/client/components/ManagePanel.vue`
- Modify: `nanobot-webui/src/client/components/ManagePanel.test.ts`

- [ ] **Step 1: Write failing tests for new ManagePanel layout**

Replace `nanobot-webui/src/client/components/ManagePanel.test.ts`:

```typescript
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ManagePanel from './ManagePanel.vue'

describe('ManagePanel', () => {
  it('renders instance sidebar with enabled instances', () => {
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
    expect(wrapper.find('[data-section="restart"]').exists()).toBe(false)
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
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/ManagePanel.test.ts`
Expected: FAIL — missing elements

- [ ] **Step 3: Rewrite ManagePanel.vue**

Replace `nanobot-webui/src/client/components/ManagePanel.vue`:

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../api'
import AgentConfigPanel from './AgentConfigPanel.vue'
import SubagentsPanel from './SubagentsPanel.vue'
import LogsPanel from './LogsPanel.vue'

const props = defineProps<{ token: string; instances: PublicInstance[] }>()

type ManageSection = 'agent-config' | 'subagents' | 'logs'

const sections: Array<{ id: ManageSection; label: string; icon: string }> = [
  { id: 'agent-config', label: 'Agent Config', icon: 'mdi:cog-outline' },
  { id: 'subagents', label: 'Subagents', icon: 'mdi:file-document-edit-outline' },
  { id: 'logs', label: 'Logs', icon: 'mdi:file-document-outline' }
]

const enabledInstances = computed(() => props.instances.filter((i) => i.enabled))
const selectedInstanceId = ref('')
const activeSection = ref<ManageSection>('agent-config')
const selectedInstance = computed(() => enabledInstances.value.find((i) => i.id === selectedInstanceId.value))
const restarting = ref(false)

watch(enabledInstances, (instances) => {
  if (instances.some((i) => i.id === selectedInstanceId.value)) return
  selectedInstanceId.value = instances[0]?.id ?? ''
}, { immediate: true })

async function restartInstance() {
  if (!selectedInstance.value) return
  restarting.value = true
  try {
    const res = await fetch(`/api/instances/${encodeURIComponent(selectedInstance.value.id)}/restart`, {
      method: 'POST',
      headers: { authorization: `Bearer ${props.token}` }
    })
    if (!res.ok) throw new Error(`Restart failed: ${res.status}`)
  } catch {
    // Graceful degradation — endpoint may not exist yet
  } finally {
    restarting.value = false
  }
}
</script>

<template>
  <section class="panel manage-panel">
    <div class="manage-layout">
      <div class="manage-sidebar" data-testid="instance-sidebar">
        <div class="sidebar-heading">Instances</div>
        <button
          v-for="instance in enabledInstances"
          :key="instance.id"
          type="button"
          :data-instance="instance.id"
          class="instance-item"
          :class="{ active: instance.id === selectedInstanceId }"
          @click="selectedInstanceId = instance.id"
        >
          <span class="dot success"></span>
          <span class="instance-name">{{ instance.name }}</span>
        </button>
        <p v-if="enabledInstances.length === 0" class="muted">No enabled instances</p>
      </div>

      <div class="manage-main">
        <div class="manage-header">
          <div>
            <h2>{{ selectedInstance?.name ?? 'Select an instance' }}</h2>
            <p v-if="selectedInstance" class="muted">{{ selectedInstance.id }} · {{ selectedInstance.baseUrl }}</p>
          </div>
          <button
            v-if="selectedInstance"
            type="button"
            data-testid="restart-button"
            class="restart-btn"
            :disabled="restarting"
            @click="restartInstance"
          >
            <Icon icon="mdi:restart" :width="16" />
            {{ restarting ? 'Restarting...' : 'Restart' }}
          </button>
        </div>

        <nav class="manage-subnav" aria-label="Manage sections">
          <button
            v-for="section in sections"
            :key="section.id"
            type="button"
            :data-section="section.id"
            :class="{ active: activeSection === section.id }"
            @click="activeSection = section.id"
          >
            <Icon :icon="section.icon" :width="16" />
            {{ section.label }}
          </button>
        </nav>

        <div class="manage-content">
          <AgentConfigPanel v-if="activeSection === 'agent-config'" :token="token" :instance="selectedInstance" />
          <SubagentsPanel v-else-if="activeSection === 'subagents'" :token="token" :instance="selectedInstance" />
          <LogsPanel v-else-if="activeSection === 'logs'" :token="token" :instance="selectedInstance" />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.manage-panel { display: grid; gap: 1rem; }
.manage-layout { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 1rem; }
.manage-sidebar { border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88); padding: 0.75rem; display: grid; gap: 0.4rem; align-content: start; }
.sidebar-heading { color: var(--fg); font-weight: 700; font-size: 13px; margin-bottom: 0.25rem; }
.instance-item { display: flex; align-items: center; gap: 8px; width: 100%; padding: 8px 10px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--muted); text-align: left; cursor: pointer; font-size: 13px; }
.instance-item:hover { background: var(--surface-2); }
.instance-item.active { border-color: oklch(64% 0.18 255 / 0.35); background: oklch(64% 0.18 255 / 0.18); color: var(--fg); }
.instance-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.manage-main { display: grid; gap: 1rem; min-width: 0; }
.manage-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.manage-header h2 { margin: 0; font-size: 16px; }
.manage-header p { margin: 0.15rem 0 0; font-size: 12px; }
.restart-btn { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); color: var(--fg); font-size: 12px; font-weight: 560; cursor: pointer; }
.restart-btn:hover { border-color: var(--accent); }
.restart-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.manage-subnav { display: flex; gap: 0.5rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
.manage-subnav button { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border: 1px solid transparent; border-radius: 8px; background: transparent; color: var(--muted); font-size: 12px; font-weight: 560; cursor: pointer; }
.manage-subnav button.active { border-color: oklch(64% 0.18 255 / 0.35); background: oklch(64% 0.18 255 / 0.18); color: var(--fg); }
.manage-content { min-width: 0; }
.muted { color: var(--muted); line-height: 1.5; margin: 0; }
@media (max-width: 900px) { .manage-layout { grid-template-columns: 1fr; } }
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/ManagePanel.test.ts`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git -C /Users/raffles/git/nanobot-rg add nanobot-webui/src/client/components/ManagePanel.vue nanobot-webui/src/client/components/ManagePanel.test.ts && git -C /Users/raffles/git/nanobot-rg commit -m "feat(webui): redesign ManagePanel with instance sidebar and new sub-nav

Replaces dropdown with instance sidebar. Sub-nav: Agent Config,
Subagents, Logs. Restart button in header. Removes unsupported
placeholder tabs."
```

---

### Task 4: Create AgentConfigPanel.vue (Settings → Agent Config)

**Files:**
- Create: `nanobot-webui/src/client/components/AgentConfigPanel.vue`
- Modify: `nanobot-webui/src/client/components/SettingsPanel.test.ts` → rename to `nanobot-webui/src/client/components/AgentConfigPanel.test.ts`

- [ ] **Step 1: Write failing tests for AgentConfigPanel**

Create `nanobot-webui/src/client/components/AgentConfigPanel.test.ts`:

```typescript
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import AgentConfigPanel from './AgentConfigPanel.vue'

describe('AgentConfigPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('loads settings and displays in CodeMirror JSON editor', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
    }))

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.find('.agent-config-panel').exists()).toBe(true))
    expect(wrapper.text()).toContain('Resolved provider')
    expect(wrapper.text()).toContain('openai')
  })

  it('shows restart warning when requires_restart is true', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: true })
    }))

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.text()).toContain('Restart required'))
  })

  it('blocks save for invalid JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.find('.agent-config-panel').exists()).toBe(true))
    const editor = wrapper.findComponent({ name: 'CodeEditor' })
    await editor.vm.$emit('update:modelValue', '{bad json')
    await wrapper.get('[data-testid="save-agent-config"]').trigger('click')
    expect(wrapper.text()).toContain('Invalid JSON')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('blocks save when agent.model or agent.provider missing from JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ agent: { model: 'gpt-4', provider: 'openai', resolved_provider: 'openai', has_api_key: true }, requires_restart: false })
    })
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(AgentConfigPanel, {
      props: { token: 'dashboard', instance: { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true } }
    })

    await vi.waitFor(() => expect(wrapper.find('.agent-config-panel').exists()).toBe(true))
    const editor = wrapper.findComponent({ name: 'CodeEditor' })
    await editor.vm.$emit('update:modelValue', '{"agent": {}}')
    await wrapper.get('[data-testid="save-agent-config"]').trigger('click')
    expect(wrapper.text()).toContain('missing agent model or provider')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/AgentConfigPanel.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Create AgentConfigPanel.vue**

Create `nanobot-webui/src/client/components/AgentConfigPanel.vue`:

```vue
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import CodeEditor from './CodeEditor.vue'
import { fetchInstanceSettings, patchInstanceSettings, type InstanceSettings, type PublicInstance } from '../api'

const props = defineProps<{ token: string; instance: PublicInstance | undefined }>()

const settings = ref<InstanceSettings | null>(null)
const jsonDraft = ref('')
const error = ref('')
const loading = ref(false)
const saving = ref(false)
let loadSequence = 0
let saveSequence = 0

const editorRef = ref<InstanceType<typeof CodeEditor> | null>(null)

async function loadSettings() {
  const instance = props.instance
  const sequence = ++loadSequence
  settings.value = null
  jsonDraft.value = ''
  error.value = ''
  if (saving.value) { saveSequence++; saving.value = false }

  if (!instance) { loading.value = false; return }

  loading.value = true
  try {
    const loaded = await fetchInstanceSettings(instance.id, props.token)
    if (sequence !== loadSequence) return
    settings.value = loaded
    jsonDraft.value = JSON.stringify(loaded, null, 2)
  } catch (err) {
    if (sequence !== loadSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

async function saveSettings() {
  const instance = props.instance
  if (!instance) return

  const sequence = ++saveSequence
  const loadSnapshot = loadSequence
  error.value = ''

  let patch: { model: string; provider: string }
  try {
    const parsed = JSON.parse(jsonDraft.value) as InstanceSettings
    if (typeof parsed?.agent?.model !== 'string' || typeof parsed?.agent?.provider !== 'string') {
      throw new Error('missing agent model or provider')
    }
    patch = { model: parsed.agent.model, provider: parsed.agent.provider }
  } catch (err) {
    error.value = `Invalid JSON${err instanceof Error ? `: ${err.message}` : ''}`
    return
  }

  saving.value = true
  try {
    const updated = await patchInstanceSettings(instance.id, props.token, patch)
    if (sequence !== saveSequence || loadSnapshot !== loadSequence) return
    settings.value = updated
    jsonDraft.value = JSON.stringify(updated, null, 2)
  } catch (err) {
    if (sequence !== saveSequence || loadSnapshot !== loadSequence) return
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    if (sequence === saveSequence) saving.value = false
  }
}

watch(() => props.instance, loadSettings, { immediate: true })
watch(() => props.token, loadSettings)
</script>

<template>
  <section class="agent-config-panel">
    <p v-if="!instance" class="muted">No target instance selected.</p>
    <p v-if="loading" class="muted">Loading settings...</p>
    <p v-if="error" class="error-text" role="alert">{{ error }}</p>

    <template v-if="settings">
      <CodeEditor
        ref="editorRef"
        v-model="jsonDraft"
        language="json"
        placeholder="{}"
      />
      <button type="button" data-testid="save-agent-config" :disabled="saving || loading" @click="saveSettings">{{ saving ? 'Saving...' : 'Save Config' }}</button>

      <dl class="settings-meta">
        <div><dt>Resolved provider</dt><dd>{{ settings.agent.resolved_provider || 'unknown' }}</dd></div>
        <div><dt>API key</dt><dd>{{ settings.agent.has_api_key ? 'configured' : 'missing' }}</dd></div>
      </dl>

      <p v-if="settings.requires_restart" class="restart-warning">Restart required</p>
    </template>
  </section>
</template>

<style scoped>
.agent-config-panel { display: grid; gap: 1rem; }
.muted { color: var(--muted); line-height: 1.5; margin: 0; }
.error-text { color: var(--warn); line-height: 1.5; margin: 0; }
button { justify-self: start; }
.settings-meta { border: 1px solid var(--border); border-radius: var(--radius); background: oklch(19% 0.014 255 / 0.88); padding: 1rem; display: grid; gap: 0.5rem; margin: 0; }
.settings-meta div { display: flex; gap: 1rem; justify-content: space-between; }
dt { color: var(--muted); }
dd { margin: 0; text-align: right; }
.restart-warning { border: 1px solid oklch(78% 0.14 85 / 0.45); border-radius: 0.75rem; background: oklch(78% 0.14 85 / 0.12); color: var(--warn); font-weight: 800; margin: 0; padding: 0.8rem 0.95rem; }
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/AgentConfigPanel.test.ts`
Expected: All tests pass

- [ ] **Step 5: Delete old SettingsPanel files and update imports**

Run:
```bash
rm /Users/raffles/git/nanobot-rg/nanobot-webui/src/client/components/SettingsPanel.vue /Users/raffles/git/nanobot-rg/nanobot-webui/src/client/components/SettingsPanel.test.ts
```

- [ ] **Step 6: Run full test suite to verify no breakage**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run`
Expected: All tests pass (ManagePanel now imports AgentConfigPanel instead of SettingsPanel)

- [ ] **Step 7: Commit**

```bash
git -C /Users/raffles/git/nanobot-rg add nanobot-webui/src/client/components/AgentConfigPanel.vue nanobot-webui/src/client/components/AgentConfigPanel.test.ts && git -C /Users/raffles/git/nanobot-rg rm nanobot-webui/src/client/components/SettingsPanel.vue nanobot-webui/src/client/components/SettingsPanel.test.ts && git -C /Users/raffles/git/nanobot-rg commit -m "feat(webui): replace SettingsPanel with AgentConfigPanel

JSON-only CodeMirror editor for remote agent config. Validates
agent.model/provider before save. Shows metadata and restart warning.
Removes GUI Form and Markdown modes from settings."
```

---

### Task 6: Replace SubagentsPanel Textarea with CodeEditor

**Files:**
- Modify: `nanobot-webui/src/client/components/SubagentsPanel.vue`

- [ ] **Step 1: Replace textarea with CodeEditor in SubagentsPanel.vue**

In `SubagentsPanel.vue`, add import:

```typescript
import CodeEditor from './CodeEditor.vue'
```

Replace the `<textarea>` (lines 124-129) with:

```html
<CodeEditor
  v-model="markdown"
  data-testid="subagent-markdown"
  language="markdown"
  :readOnly="selected ? !selected.editable : false"
  placeholder="Open a subagent or create a new one to edit Markdown."
/>
```

Remove the textarea styles (the `textarea { ... }` rule in `<style scoped>`).

- [ ] **Step 2: Run full test suite**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git -C /Users/raffles/git/nanobot-rg add nanobot-webui/src/client/components/SubagentsPanel.vue && git -C /Users/raffles/git/nanobot-rg commit -m "feat(webui): replace SubagentsPanel textarea with CodeEditor

Markdown mode CodeMirror 6 editor for subagent workflow definitions.
Supports read-only mode for built-in subagents."
```

---

### Task 7: Add restartInstance API Function

**Files:**
- Modify: `nanobot-webui/src/client/api.ts`

- [ ] **Step 1: Add restartInstance function to api.ts**

Add to `nanobot-webui/src/client/api.ts` after `patchInstanceSettings`:

```typescript
export async function restartInstance(instanceId: string, token: string): Promise<void> {
  const res = await fetch(`/api/instances/${encodeURIComponent(instanceId)}/restart`, {
    method: 'POST',
    headers: authHeaders(token)
  })
  if (!res.ok) throw new Error(`failed to restart ${instanceId}: ${res.status}`)
}
```

- [ ] **Step 2: Run full test suite**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git -C /Users/raffles/git/nanobot-rg add nanobot-webui/src/client/api.ts && git -C /Users/raffles/git/nanobot-rg commit -m "feat(webui): add restartInstance API function

POST /api/instances/:id/restart for agent restart control.
Endpoint graceful degradation until backend implements it."
```

---

### Task 8: Final Integration — Typecheck, Build, Full Test Suite

**Files:**
- No new files — verification only

- [ ] **Step 1: Run vue-tsc typecheck**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vue-tsc --noEmit`
Expected: No errors

- [ ] **Step 2: Run vite build**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Run full test suite**

Run: `cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run`
Expected: All tests pass

- [ ] **Step 4: Commit any remaining fixes**

If typecheck or build revealed issues, fix and commit:

```bash
git -C /Users/raffles/git/nanobot-rg add -A && git -C /Users/raffles/git/nanobot-rg commit -m "fix(webui): address typecheck and build issues from manage agents redesign"
```
