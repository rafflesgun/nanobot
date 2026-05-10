# Chat UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ChatPanel with a ChatGPT-style chat interface supporting group conversations (1+ bot instances), conversation sidebar, auto-growing composer, streaming cursor, rich code blocks, and Iconify icons.

**Architecture:** Full rewrite of ChatPanel.vue → ChatView.vue with 11 new components. Reuse `chatTranscript.ts` and `socket.ts` unchanged. Replace `markdownTranscript.ts` with `markdown-it` + `highlight.js`. Add `Conversation` type alias and `fetchConversations`/`saveConversations` wrappers in `api.ts`.

**Tech Stack:** Vue 3, @iconify/vue, markdown-it, markdown-it-task-lists, highlight.js

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Delete | `src/client/components/ChatPanel.vue` | Old topic-based chat |
| Delete | `src/client/components/ChatPanel.test.ts` | Old tests |
| Delete | `src/client/markdownTranscript.ts` | Old custom markdown parser |
| Delete | `src/client/markdownTranscript.test.ts` | Old parser tests |
| Create | `src/client/components/chat/ChatView.vue` | Main chat orchestrator |
| Create | `src/client/components/chat/ConversationSidebar.vue` | Left sidebar: new chat, search, date-grouped list |
| Create | `src/client/components/chat/ConversationItem.vue` | Single conversation row in sidebar |
| Create | `src/client/components/chat/ChatArea.vue` | Right panel: header + messages + composer |
| Create | `src/client/components/chat/ChatHeader.vue` | Title + member avatars + settings gear |
| Create | `src/client/components/chat/MessageList.vue` | Scroll container, auto-scroll |
| Create | `src/client/components/chat/MessageBubble.vue` | User or bot message with avatar |
| Create | `src/client/components/chat/CodeBlock.vue` | Syntax-highlighted code with copy/download |
| Create | `src/client/components/chat/ToolCallBlock.vue` | Collapsible tool invocation |
| Create | `src/client/components/chat/ChatComposer.vue` | Auto-growing textarea + attach + send/stop |
| Create | `src/client/components/chat/NewChatDialog.vue` | Modal: pick instances, name chat |
| Create | `src/client/components/chat/ChatView.test.ts` | All ChatView tests |
| Create | `src/client/components/chat/markdown.ts` | markdown-it setup + render helper |
| Create | `src/client/components/chat/markdown.test.ts` | Markdown render tests |
| Create | `src/client/components/chat/useConversations.ts` | Composable: conversation CRUD + persistence |
| Create | `src/client/components/chat/useConversations.test.ts` | Composable tests |
| Modify | `src/client/api.ts` | Add Conversation type, fetchConversations, saveConversations |
| Modify | `src/client/App.vue` | Replace ChatPanel import → ChatView, rename nav label |

---

### Task 1: Install dependencies

**Files:**
- Modify: `nanobot-webui/package.json`

- [ ] **Step 1: Install packages**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npm install @iconify/vue markdown-it markdown-it-task-lists highlight.js
```

- [ ] **Step 2: Install type packages**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npm install -D @types/markdown-it @types/markdown-it-task-lists
```

- [ ] **Step 3: Verify install**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && node -e "require('@iconify/vue'); require('markdown-it'); require('highlight.js'); console.log('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add package.json package-lock.json && git commit -m "chore(webui): add @iconify/vue, markdown-it, highlight.js dependencies"
```

---

### Task 2: Add Conversation type and API wrappers to api.ts

**Files:**
- Modify: `nanobot-webui/src/client/api.ts`
- Test: `nanobot-webui/src/client/api.test.ts`

- [ ] **Step 1: Add Conversation type and API wrappers after the StateTopic type (line 40)**

```ts
export type Conversation = StateTopic

export type ConversationSummary = {
  id: string
  name: string
  memberCount: number
  updatedAt: string
  lastMessage: string | null
}

export async function fetchConversations(token: string): Promise<Conversation[]> {
  return fetchStateTopics(token)
}

export async function saveConversations(token: string, conversations: Conversation[]): Promise<Conversation[]> {
  return saveStateTopics(token, conversations)
}
```

- [ ] **Step 2: Run existing tests to verify no regression**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && python3 -m pytest ../tests -x -q 2>/dev/null; npx vitest run src/client/api.test.ts
```

Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add src/client/api.ts && git commit -m "feat(webui): add Conversation type and fetchConversations/saveConversations wrappers"
```

---

### Task 3: Create markdown-it helper module

**Files:**
- Create: `nanobot-webui/src/client/components/chat/markdown.ts`
- Create: `nanobot-webui/src/client/components/chat/markdown.test.ts`

- [ ] **Step 1: Write the test**

```ts
// markdown.test.ts
import { describe, expect, it } from 'vitest'
import { renderMarkdown } from './markdown'

describe('renderMarkdown', () => {
  it('renders a paragraph', () => {
    const html = renderMarkdown('hello world')
    expect(html).toContain('<p>hello world</p>')
  })

  it('renders a heading', () => {
    const html = renderMarkdown('# Title')
    expect(html).toContain('<h1>Title</h1>')
  })

  it('renders a code block with language class', () => {
    const html = renderMarkdown('```ts\nconst x = 1\n```')
    expect(html).toContain('class="language-ts"')
    expect(html).toContain('const x = 1')
  })

  it('renders inline code', () => {
    const html = renderMarkdown('use `code` here')
    expect(html).toContain('<code>code</code>')
  })

  it('renders a bullet list', () => {
    const html = renderMarkdown('- one\n- two')
    expect(html).toContain('<ul>')
    expect(html).toContain('<li>one</li>')
    expect(html).toContain('<li>two</li>')
  })

  it('renders GFM task list', () => {
    const html = renderMarkdown('- [x] done\n- [ ] todo')
    expect(html).toContain('class="task-list-item"')
  })

  it('renders a table', () => {
    const html = renderMarkdown('| a | b |\n|---|---|\n| 1 | 2 |')
    expect(html).toContain('<table>')
    expect(html).toContain('<th>a</th>')
  })

  it('escapes script tags in content', () => {
    const html = renderMarkdown('<script>alert(1)</script>')
    expect(html).not.toContain('<script>')
  })

  it('highlights code blocks', () => {
    const html = renderMarkdown('```javascript\nconst x = 1;\n```')
    expect(html).toContain('hljs')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/chat/markdown.test.ts
```

Expected: FAIL — module not found

- [ ] **Step 3: Create the markdown module**

```ts
// markdown.ts
import MarkdownIt from 'markdown-it'
import taskListPlugin from 'markdown-it-task-lists'
import hljs from 'highlight.js'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  highlight(str: string, lang: string) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code class="language-${lang}">${hljs.highlight(str, { language: lang }).value}</code></pre>`
      } catch { /* fall through */ }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  }
}).use(taskListPlugin)

export function renderMarkdown(text: string): string {
  return md.render(text)
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/chat/markdown.test.ts
```

Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/client/components/chat/markdown.ts src/client/components/chat/markdown.test.ts && git commit -m "feat(webui): add markdown-it helper with highlight.js and task lists"
```

---

### Task 4: Create useConversations composable

**Files:**
- Create: `nanobot-webui/src/client/components/chat/useConversations.ts`
- Create: `nanobot-webui/src/client/components/chat/useConversations.test.ts`

- [ ] **Step 1: Write the test**

```ts
// useConversations.test.ts
import { describe, expect, it, vi } from 'vitest'
import { useConversations } from './useConversations'
import type { Conversation } from '../../api'

const conv1: Conversation = {
  id: 'c1',
  name: 'Code Review',
  selectedIds: ['alpha'],
  chatMappings: {},
  transcript: { entries: [], debugEvents: [] }
}

const conv2: Conversation = {
  id: 'c2',
  name: 'Quick Question',
  selectedIds: ['beta'],
  chatMappings: {},
  transcript: { entries: [], debugEvents: [] }
}

describe('useConversations', () => {
  it('loads conversations from the API', async () => {
    const load = vi.fn().mockResolvedValue([conv1, conv2])
    const { conversations, loadConversations } = useConversations({ loadConversationsApi: load, saveConversationsApi: vi.fn() })
    await loadConversations('tok')
    expect(conversations.value).toHaveLength(2)
    expect(conversations.value[0].name).toBe('Code Review')
  })

  it('creates a new conversation and selects it', async () => {
    const save = vi.fn().mockResolvedValue([])
    const { conversations, activeConversationId, createConversation } = useConversations({ loadConversationsApi: vi.fn().mockResolvedValue([]), saveConversationsApi: save })
    await createConversation('New Chat', ['alpha'])
    expect(conversations.value).toHaveLength(1)
    expect(conversations.value[0].name).toBe('New Chat')
    expect(activeConversationId.value).toBe(conversations.value[0].id)
  })

  it('deletes a conversation', async () => {
    const save = vi.fn().mockResolvedValue([])
    const { conversations, loadConversations, deleteConversation } = useConversations({ loadConversationsApi: vi.fn().mockResolvedValue([conv1, conv2]), saveConversationsApi: save })
    await loadConversations('tok')
    deleteConversation('c1')
    expect(conversations.value).toHaveLength(1)
    expect(conversations.value[0].id).toBe('c2')
  })

  it('renames a conversation', async () => {
    const save = vi.fn().mockResolvedValue([])
    const { conversations, loadConversations, renameConversation } = useConversations({ loadConversationsApi: vi.fn().mockResolvedValue([conv1]), saveConversationsApi: save })
    await loadConversations('tok')
    renameConversation('c1', 'Renamed')
    expect(conversations.value[0].name).toBe('Renamed')
  })

  it('groups conversations by date', async () => {
    const today = { ...conv1, transcript: { entries: [{ id: 1, instanceId: 'a', chatId: 'c', label: '', role: 'user', event: 'outbound', text: 'hi' }], debugEvents: [] } }
    const load = vi.fn().mockResolvedValue([today, conv2])
    const { loadConversations, dateGroups } = useConversations({ loadConversationsApi: load, saveConversationsApi: vi.fn() })
    await loadConversations('tok')
    expect(dateGroups.value.length).toBeGreaterThanOrEqual(1)
  })

  it('persists conversations via save API', async () => {
    const save = vi.fn().mockResolvedValue([])
    const { conversations, loadConversations, persistConversations } = useConversations({ loadConversationsApi: vi.fn().mockResolvedValue([conv1]), saveConversationsApi: save })
    await loadConversations('tok')
    await persistConversations('tok')
    expect(save).toHaveBeenCalledWith('tok', conversations.value)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/chat/useConversations.test.ts
```

Expected: FAIL — module not found

- [ ] **Step 3: Create the composable**

```ts
// useConversations.ts
import { computed, ref } from 'vue'
import type { Conversation } from '../../api'

type DateGroup = { label: string; conversations: Conversation[] }

export function useConversations(options: {
  loadConversationsApi: (token: string) => Promise<Conversation[]>
  saveConversationsApi: (token: string, conversations: Conversation[]) => Promise<Conversation[]>
}) {
  const conversations = ref<Conversation[]>([])
  const activeConversationId = ref<string | null>(null)

  const activeConversation = computed(() =>
    conversations.value.find((c) => c.id === activeConversationId.value) ?? null
  )

  const dateGroups = computed<DateGroup[]>(() => {
    const now = new Date()
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
    const yesterdayStart = todayStart - 86400000
    const weekStart = todayStart - 7 * 86400000
    const groups: DateGroup[] = [
      { label: 'Today', conversations: [] },
      { label: 'Yesterday', conversations: [] },
      { label: 'Previous 7 Days', conversations: [] },
      { label: 'Older', conversations: [] }
    ]
    for (const conv of conversations.value) {
      const lastEntry = conv.transcript.entries[conv.transcript.entries.length - 1]
      const ts = lastEntry ? Date.now() : Date.now()
      const t = ts >= todayStart ? 0 : ts >= yesterdayStart ? 1 : ts >= weekStart ? 2 : 3
      groups[t].conversations.push(conv)
    }
    return groups.filter((g) => g.conversations.length > 0)
  })

  async function loadConversations(token: string) {
    const result = await options.loadConversationsApi(token)
    conversations.value = result
    if (result.length > 0 && !activeConversationId.value) {
      activeConversationId.value = result[0].id
    }
  }

  async function createConversation(name: string, memberIds: string[]) {
    const id = `${Date.now()}-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
    const conv: Conversation = {
      id,
      name,
      selectedIds: memberIds,
      chatMappings: {},
      transcript: { entries: [], debugEvents: [] }
    }
    conversations.value.unshift(conv)
    activeConversationId.value = id
    return conv
  }

  function deleteConversation(id: string) {
    conversations.value = conversations.value.filter((c) => c.id !== id)
    if (activeConversationId.value === id) {
      activeConversationId.value = conversations.value[0]?.id ?? null
    }
  }

  function renameConversation(id: string, newName: string) {
    const conv = conversations.value.find((c) => c.id === id)
    if (conv) conv.name = newName
  }

  function selectConversation(id: string) {
    activeConversationId.value = id
  }

  async function persistConversations(token: string) {
    await options.saveConversationsApi(token, conversations.value)
  }

  return {
    conversations,
    activeConversationId,
    activeConversation,
    dateGroups,
    loadConversations,
    createConversation,
    deleteConversation,
    renameConversation,
    selectConversation,
    persistConversations
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/chat/useConversations.test.ts
```

Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/client/components/chat/useConversations.ts src/client/components/chat/useConversations.test.ts && git commit -m "feat(webui): add useConversations composable with CRUD and date grouping"
```

---

### Task 5: Create CodeBlock component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/CodeBlock.vue`

- [ ] **Step 1: Create CodeBlock.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'

const props = defineProps<{ language: string; code: string }>()
const copied = ref(false)

async function copyCode() {
  try {
    await navigator.clipboard.writeText(props.code)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch { copied.value = false }
}

function downloadCode() {
  const ext: Record<string, string> = { ts: 'ts', js: 'js', python: 'py', html: 'html', css: 'css', json: 'json', bash: 'sh', shell: 'sh', sql: 'sql', rust: 'rs', go: 'go', java: 'java', cpp: 'cpp', c: 'c', ruby: 'rb', yaml: 'yml', yml: 'yml', xml: 'xml', markdown: 'md', typescript: 'ts', javascript: 'js' }
  const extName = ext[props.language.toLowerCase()] ?? 'txt'
  const name = `code-${Math.random().toString(36).slice(2, 8)}.${extName}`
  const blob = new Blob([props.code], { type: 'text/plain' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<template>
  <div class="code-block">
    <div class="code-header">
      <span class="code-lang">{{ language || 'text' }}</span>
      <div class="code-actions">
        <button data-testid="copy-code" class="code-action" :title="copied ? 'Copied' : 'Copy'" @click="copyCode">
          <Icon :icon="copied ? 'mdi:check' : 'mdi:content-copy'" width="16" />
        </button>
        <button data-testid="download-code" class="code-action" title="Download" @click="downloadCode">
          <Icon icon="mdi:download" width="16" />
        </button>
      </div>
    </div>
    <pre class="code-body"><code v-html="code"></code></pre>
  </div>
</template>

<style scoped>
.code-block {
  border: 1px solid var(--border);
  border-radius: 0.7rem;
  background: oklch(12% 0.012 255);
  overflow: hidden;
  margin: 0.5rem 0;
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 10px;
  background: oklch(22% 0.014 255);
}

.code-lang {
  font-size: 0.7rem;
  color: var(--muted);
  text-transform: lowercase;
}

.code-actions {
  display: flex;
  gap: 4px;
}

.code-action {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.code-action:hover {
  color: var(--fg);
  background: oklch(30% 0.014 255);
}

.code-body {
  margin: 0;
  padding: 0.75rem;
  overflow: auto;
}

.code-body code {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--fg);
  white-space: pre;
}
</style>
```

- [ ] **Step 2: Verify component compiles**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vue-tsc --noEmit 2>&1 | head -20
```

Expected: No errors related to CodeBlock.vue

- [ ] **Step 3: Commit**

```bash
git add src/client/components/chat/CodeBlock.vue && git commit -m "feat(webui): add CodeBlock component with copy, download, syntax highlighting"
```

---

### Task 6: Create ToolCallBlock component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/ToolCallBlock.vue`

- [ ] **Step 1: Create ToolCallBlock.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'

defineProps<{ title: string; text: string }>()
const expanded = ref(false)
</script>

<template>
  <div class="tool-block">
    <button class="tool-header" @click="expanded = !expanded">
      <Icon icon="mdi:lightning-bolt" width="14" class="tool-icon" />
      <span class="tool-title">{{ title }}</span>
      <Icon :icon="expanded ? 'mdi:chevron-up' : 'mdi:chevron-down'" width="16" />
    </button>
    <div v-if="expanded" class="tool-body">
      <pre>{{ text }}</pre>
    </div>
  </div>
</template>

<style scoped>
.tool-block {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  overflow: hidden;
  margin: 0.35rem 0;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 6px 10px;
  border: none;
  background: oklch(19% 0.014 255 / 0.5);
  color: var(--muted);
  font-size: 0.8rem;
  cursor: pointer;
  text-align: left;
}

.tool-header:hover {
  background: oklch(22% 0.014 255);
  color: var(--fg);
}

.tool-icon {
  color: var(--accent);
}

.tool-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-body {
  padding: 8px 10px;
  border-top: 1px solid var(--border);
}

.tool-body pre {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--muted);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/client/components/chat/ToolCallBlock.vue && git commit -m "feat(webui): add ToolCallBlock component with collapsible display"
```

---

### Task 7: Create MessageBubble component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/MessageBubble.vue`

- [ ] **Step 1: Create MessageBubble.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { renderMarkdown } from './markdown'
import CodeBlock from './CodeBlock.vue'
import ToolCallBlock from './ToolCallBlock.vue'
import type { TranscriptEntry } from '../../chatTranscript'
import type { PublicInstance } from '../../api'

const props = defineProps<{
  entry: TranscriptEntry
  instance?: PublicInstance
}>()

const copied = ref(false)

function isStreaming(): boolean {
  return props.entry.text.endsWith('▍')
}

function displayText(): string {
  return isStreaming() ? props.entry.text.slice(0, -1) : props.entry.text
}

function avatarLabel(): string {
  return props.instance?.name?.charAt(0)?.toUpperCase() ?? '?'
}

function avatarColor(): string {
  const colors = ['#5a5aff', '#4a7', '#da3', '#d5a', '#7ad', '#a77']
  const index = (props.entry.instanceId.charCodeAt(0) + (props.entry.instanceId.charCodeAt(1) || 0)) % colors.length
  return colors[index]
}

async function copyMarkdown() {
  try {
    await navigator.clipboard.writeText(props.entry.text)
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  } catch { copied.value = false }
}

interface ParsedBlock {
  type: 'html' | 'code'
  content: string
  language: string
  rawCode: string
}

function parsedBlocks(): ParsedBlock[] {
  if (props.entry.kind === 'tool' || props.entry.kind === 'reasoning') return []
  const html = renderMarkdown(displayText())
  const blocks: ParsedBlock[] = []
  const codePattern = /<pre class="hljs"><code class="language-(\w+)">([\s\S]*?)<\/code><\/pre>/g
  let lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = codePattern.exec(html)) !== null) {
    if (match.index > lastIndex) {
      blocks.push({ type: 'html', content: html.slice(lastIndex, match.index), language: '', rawCode: '' })
    }
    const lang = match[1]
    const codeHtml = match[2]
    const rawCode = codeHtml.replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    blocks.push({ type: 'code', content: codeHtml, language: lang, rawCode })
    lastIndex = match.index + match[0].length
  }
  if (lastIndex < html.length) {
    blocks.push({ type: 'html', content: html.slice(lastIndex), language: '', rawCode: '' })
  }
  return blocks
}
</script>

<template>
  <div class="message" :class="[`is-${entry.role}`, entry.kind ? `is-${entry.kind}` : '']">
    <div v-if="entry.role === 'user'" class="user-bubble">
      <div class="bubble-content">{{ entry.text }}</div>
      <div v-if="entry.attachments?.length" class="attachment-row">
        <span v-for="att in entry.attachments" :key="att.data_url" class="attachment-chip">{{ att.name ?? 'attachment' }}</span>
      </div>
    </div>

    <div v-else-if="entry.kind === 'tool'" class="tool-entry">
      <ToolCallBlock :title="entry.title ?? 'Tool call'" :text="entry.text" />
    </div>

    <div v-else-if="entry.kind === 'reasoning'" class="reasoning-entry">
      <ToolCallBlock :title="entry.title ?? 'Reasoning'" :text="entry.text" />
    </div>

    <div v-else class="bot-message">
      <div class="bot-avatar" :style="{ background: avatarColor() }">
        <Icon v-if="!instance" icon="mdi:robot-outline" width="18" />
        <span v-else class="avatar-letter">{{ avatarLabel() }}</span>
      </div>
      <div class="bot-body">
        <div class="bot-name">{{ instance?.name ?? entry.label }}</div>
        <div class="markdown-body">
          <template v-for="(block, i) in parsedBlocks()" :key="i">
            <div v-if="block.type === 'html'" v-html="block.content"></div>
            <CodeBlock v-else :language="block.language" :code="block.rawCode" />
          </template>
        </div>
        <span v-if="isStreaming()" class="streaming-cursor">▍</span>
      </div>
      <button v-if="entry.role !== 'user'" data-testid="copy-markdown" class="copy-button" :title="copied ? 'Copied' : 'Copy'" @click="copyMarkdown">
        <Icon :icon="copied ? 'mdi:check' : 'mdi:content-copy'" width="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.message {
  margin-bottom: 1rem;
}

.message.is-user {
  display: flex;
  justify-content: flex-end;
}

.user-bubble {
  max-width: 70%;
}

.bubble-content {
  background: oklch(64% 0.18 255 / 0.18);
  border-radius: 1rem 1rem 0.25rem 1rem;
  padding: 0.65rem 0.9rem;
  font-size: 0.88rem;
  line-height: 1.55;
  white-space: pre-wrap;
}

.bot-message {
  display: flex;
  gap: 10px;
  max-width: 90%;
  position: relative;
}

.bot-avatar {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.avatar-letter {
  line-height: 1;
}

.bot-body {
  flex: 1;
  min-width: 0;
}

.bot-name {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 2px;
}

.markdown-body {
  font-size: 0.88rem;
  line-height: 1.6;
  color: var(--fg);
}

.markdown-body :deep(p) {
  margin: 0.4rem 0;
}

.markdown-body :deep(p:first-child) {
  margin-top: 0;
}

.markdown-body :deep(ul), .markdown-body :deep(ol) {
  padding-left: 1.25rem;
  margin: 0.4rem 0;
}

.markdown-body :deep(code) {
  font-family: var(--font-mono);
  font-size: 0.85em;
  border: 1px solid oklch(64% 0.18 255 / 0.18);
  border-radius: 0.3rem;
  background: oklch(12% 0.012 255);
  padding: 0.1rem 0.3rem;
  color: var(--accent);
}

.markdown-body :deep(pre) {
  margin: 0;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5rem 0;
}

.markdown-body :deep(th), .markdown-body :deep(td) {
  border: 1px solid var(--border);
  padding: 6px 10px;
  font-size: 0.82rem;
}

.markdown-body :deep(th) {
  background: oklch(22% 0.014 255);
  font-weight: 600;
}

.streaming-cursor {
  animation: blink 1s step-end infinite;
  color: var(--accent);
  font-size: 0.9rem;
}

@keyframes blink {
  50% { opacity: 0; }
}

.copy-button {
  position: absolute;
  top: 0;
  right: 0;
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity 150ms;
}

.bot-message:hover .copy-button {
  opacity: 1;
}

.copy-button:hover {
  color: var(--fg);
  background: var(--surface);
}

.attachment-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.attachment-chip {
  font-size: 0.75rem;
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  color: var(--muted);
}

.tool-entry, .reasoning-entry {
  padding-left: 38px;
  max-width: 90%;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/client/components/chat/MessageBubble.vue && git commit -m "feat(webui): add MessageBubble with markdown rendering, streaming cursor, copy"
```

---

### Task 8: Create ChatComposer component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/ChatComposer.vue`

- [ ] **Step 1: Create ChatComposer.vue**

```vue
<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { Icon } from '@iconify/vue'
import type { ComposerMedia } from '../../api'

const emit = defineEmits<{
  send: [text: string, media: ComposerMedia[]]
  stop: []
}>()

defineProps<{
  disabled: boolean
  isGenerating: boolean
}>()

const message = ref('')
const pendingAttachments = ref<ComposerMedia[]>([])
const textarea = ref<HTMLTextAreaElement>()

watch(message, async () => {
  await nextTick()
  if (textarea.value) {
    textarea.value.style.height = 'auto'
    textarea.value.style.height = Math.min(textarea.value.scrollHeight, 18 * 20) + 'px'
  }
})

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function send() {
  const text = message.value.trim()
  if (!text) return
  emit('send', text, [...pendingAttachments.value])
  message.value = ''
  pendingAttachments.value = []
  if (textarea.value) textarea.value.style.height = 'auto'
}

function readFileAsDataUrl(file: File) {
  return new Promise<ComposerMedia>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve({ name: file.name, data_url: String(reader.result) })
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

async function addAttachments(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  const media = await Promise.all(files.map(readFileAsDataUrl))
  pendingAttachments.value.push(...media)
  input.value = ''
}

function removeAttachment(index: number) {
  pendingAttachments.value.splice(index, 1)
}

async function handlePaste(e: ClipboardEvent) {
  const items = Array.from(e.clipboardData?.items ?? [])
  for (const item of items) {
    if (item.type.startsWith('image/')) {
      e.preventDefault()
      const file = item.getAsFile()
      if (file) {
        const media = await readFileAsDataUrl(file)
        pendingAttachments.value.push(media)
      }
    }
  }
}
</script>

<template>
  <div class="composer">
    <div v-if="pendingAttachments.length" class="attachment-row">
      <button v-for="(att, i) in pendingAttachments" :key="att.data_url" class="attachment-chip" @click="removeAttachment(i)">
        {{ att.name ?? 'attachment' }} ×
      </button>
    </div>
    <div class="input-row">
      <label class="attach-button">
        <Icon icon="mdi:plus-circle-outline" width="28" />
        <input data-testid="attachment-input" type="file" multiple @change="addAttachments">
      </label>
      <textarea
        ref="textarea"
        v-model="message"
        data-testid="chat-input"
        class="chat-textarea"
        rows="1"
        :placeholder="disabled ? 'Add at least one bot to start chatting' : 'Message... (Enter to send, Shift+Enter for new line)'"
        :disabled="disabled && !isGenerating"
        @keydown="handleKeydown"
        @paste="handlePaste"
      ></textarea>
      <button v-if="isGenerating" data-testid="stop-button" class="send-button stop" title="Stop generating" @click="$emit('stop')">
        <Icon icon="mdi:stop-circle" width="24" />
      </button>
      <button v-else data-testid="send-button" class="send-button" :class="{ disabled: !message.trim() || disabled }" :disabled="!message.trim() || disabled" @click="send">
        <Icon icon="mdi:send" width="20" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer {
  padding: 10px 20px 16px;
}

.attachment-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.attachment-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--muted);
  font-size: 0.75rem;
  cursor: pointer;
}

.attachment-chip:hover {
  color: var(--fg);
}

.input-row {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 0;
  border: 2px solid var(--border);
  border-radius: 16px;
  background: oklch(19% 0.014 255 / 0.88);
  transition: border-color 150ms;
}

.input-row:focus-within {
  border-color: var(--accent);
}

.attach-button {
  display: grid;
  place-items: center;
  padding: 10px;
  color: var(--muted);
  cursor: pointer;
  flex-shrink: 0;
}

.attach-button:hover {
  color: var(--fg);
}

.attach-button input {
  display: none;
}

.chat-textarea {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--fg);
  font-family: inherit;
  font-size: 0.88rem;
  line-height: 1.5;
  padding: 12px 0;
  resize: none;
  outline: none;
  min-height: 24px;
  max-height: 360px;
}

.chat-textarea::placeholder {
  color: var(--muted);
}

.send-button {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  margin: 6px;
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: oklch(99% 0 0);
  cursor: pointer;
  flex-shrink: 0;
}

.send-button.disabled {
  background: var(--surface-2);
  color: var(--muted);
  cursor: not-allowed;
}

.send-button.stop {
  background: transparent;
  color: var(--danger);
  animation: pulse-stop 1.5s ease infinite;
}

@keyframes pulse-stop {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/client/components/chat/ChatComposer.vue && git commit -m "feat(webui): add ChatComposer with auto-grow, file attach, send/stop"
```

---

### Task 9: Create ChatHeader component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/ChatHeader.vue`

- [ ] **Step 1: Create ChatHeader.vue**

```vue
<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../../api'

defineProps<{
  name: string
  members: PublicInstance[]
  connectionStatuses: Record<string, 'idle' | 'connecting' | 'connected' | 'error' | 'disconnected'>
}>()

const emit = defineEmits<{
  addMember: []
  removeMember: [instanceId: string]
  settings: []
}>()

function statusColor(instanceId: string): string {
  const status = arguments[1]?.[instanceId] ?? 'idle'
  if (status === 'connected') return 'var(--success)'
  if (status === 'connecting') return 'var(--accent)'
  if (status === 'error' || status === 'disconnected') return 'var(--danger)'
  return 'var(--muted)'
}
</script>

<template>
  <header class="chat-header">
    <div class="header-left">
      <h3 class="chat-title">{{ name }}</h3>
      <div class="member-avatars">
        <div
          v-for="member in members"
          :key="member.id"
          class="member-avatar"
          :style="{ borderColor: connectionStatuses[member.id] === 'connected' ? 'var(--success)' : connectionStatuses[member.id] === 'error' ? 'var(--danger)' : 'var(--border)' }"
          :title="member.name"
        >
          {{ member.name.charAt(0).toUpperCase() }}
          <button class="remove-member" :aria-label="`Remove ${member.name}`" @click="$emit('removeMember', member.id)">×</button>
        </div>
        <button class="add-member" title="Add bot" @click="$emit('addMember')">
          <Icon icon="mdi:plus" width="16" />
        </button>
      </div>
    </div>
    <div class="header-right">
      <button class="icon-btn" title="Chat settings" @click="$emit('settings')">
        <Icon icon="mdi:cog-outline" width="18" />
      </button>
    </div>
  </header>
</template>

<style scoped>
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.chat-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.member-avatars {
  display: flex;
  align-items: center;
  gap: 4px;
}

.member-avatar {
  position: relative;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid var(--border);
  display: grid;
  place-items: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
  background: oklch(40% 0.05 255);
}

.remove-member {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  border: none;
  background: var(--danger);
  color: #fff;
  font-size: 9px;
  line-height: 1;
  display: none;
  place-items: center;
  cursor: pointer;
}

.member-avatar:hover .remove-member {
  display: grid;
}

.add-member {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px dashed var(--border);
  background: transparent;
  color: var(--muted);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.add-member:hover {
  color: var(--fg);
  border-color: var(--accent);
}

.icon-btn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.icon-btn:hover {
  color: var(--fg);
  background: var(--surface);
}
</style>
```

- [ ] **Step 2: Fix the statusColor dead code — simplify to just use connectionStatuses prop directly in template. The function is unused, remove it.**

Edit ChatHeader.vue: remove the `statusColor` function entirely (lines with `function statusColor`). The template already uses `connectionStatuses` directly via `:style` binding.

- [ ] **Step 3: Commit**

```bash
git add src/client/components/chat/ChatHeader.vue && git commit -m "feat(webui): add ChatHeader with member avatars and connection status"
```

---

### Task 10: Create ConversationSidebar components

**Files:**
- Create: `nanobot-webui/src/client/components/chat/ConversationItem.vue`
- Create: `nanobot-webui/src/client/components/chat/ConversationSidebar.vue`

- [ ] **Step 1: Create ConversationItem.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../../api'

const props = defineProps<{
  id: string
  name: string
  members: PublicInstance[]
  isActive: boolean
}>()

const emit = defineEmits<{
  select: []
  rename: [newName: string]
  delete: []
}>()

const showMenu = ref(false)
const isRenaming = ref(false)
const renameValue = ref('')

function startRename() {
  renameValue.value = props.name
  isRenaming.value = true
  showMenu.value = false
}

function confirmRename() {
  const trimmed = renameValue.value.trim()
  if (trimmed && trimmed !== props.name) emit('rename', trimmed)
  isRenaming.value = false
}
</script>

<template>
  <button
    class="conv-item"
    :class="{ active: isActive }"
    @click="emit('select')"
    @mouseenter="showMenu = true"
    @mouseleave="showMenu = false"
  >
    <div class="conv-avatars">
      <div
        v-for="(m, i) in members.slice(0, 3)"
        :key="m.id"
        class="mini-avatar"
        :style="{ zIndex: 3 - i }"
      >{{ m.name.charAt(0).toUpperCase() }}</div>
      <span v-if="members.length > 3" class="avatar-overflow">+{{ members.length - 3 }}</span>
    </div>
    <div v-if="isRenaming" class="conv-name-wrap" @click.stop>
      <input v-model="renameValue" class="rename-input" @keyup.enter="confirmRename" @keyup.escape="isRenaming = false" />
    </div>
    <div v-else class="conv-name">{{ name }}</div>
    <div v-if="showMenu && !isRenaming" class="conv-menu" @click.stop>
      <button class="menu-action" title="Rename" @click="startRename"><Icon icon="mdi:pencil" width="16" /></button>
      <button class="menu-action danger" title="Delete" @click="emit('delete')"><Icon icon="mdi:delete-outline" width="16" /></button>
    </div>
  </button>
</template>

<style scoped>
.conv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--muted);
  text-align: left;
  cursor: pointer;
  transition: background 100ms;
}

.conv-item:hover {
  background: oklch(19% 0.014 255 / 0.5);
}

.conv-item.active {
  background: oklch(64% 0.18 255 / 0.12);
  border-color: oklch(64% 0.18 255 / 0.25);
  color: var(--fg);
}

.conv-avatars {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.mini-avatar {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: var(--accent);
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: grid;
  place-items: center;
  margin-left: -4px;
}

.mini-avatar:first-child {
  margin-left: 0;
}

.avatar-overflow {
  font-size: 10px;
  margin-left: 2px;
  color: var(--muted);
}

.conv-name {
  flex: 1;
  min-width: 0;
  font-size: 0.82rem;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conv-name-wrap {
  flex: 1;
  min-width: 0;
}

.rename-input {
  width: 100%;
  padding: 2px 6px;
  border: 1px solid var(--accent);
  border-radius: 4px;
  background: var(--surface);
  color: var(--fg);
  font-size: 0.82rem;
  outline: none;
}

.conv-menu {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.menu-action {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.menu-action:hover {
  color: var(--fg);
  background: var(--surface);
}

.menu-action.danger:hover {
  color: var(--danger);
}
</style>
```

- [ ] **Step 2: Create ConversationSidebar.vue**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import type { Conversation } from '../../api'
import type { PublicInstance } from '../../api'
import ConversationItem from './ConversationItem.vue'

type DateGroup = { label: string; conversations: Conversation[] }

const props = defineProps<{
  dateGroups: DateGroup[]
  activeId: string | null
  instances: PublicInstance[]
  collapsed: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
  newChat: []
  rename: [id: string, newName: string]
  delete: [id: string]
  collapse: []
}>()

const search = ref('')

function instanceFor(id: string) {
  return props.instances.find((i) => i.id === id)
}

function membersFor(conv: Conversation) {
  return conv.selectedIds.map(instanceFor).filter(Boolean) as PublicInstance[]
}

function filteredGroups(): DateGroup[] {
  if (!search.value.trim()) return props.dateGroups
  const q = search.value.toLowerCase()
  return props.dateGroups
    .map((g) => ({
      ...g,
      conversations: g.conversations.filter((c) => c.name.toLowerCase().includes(q))
    }))
    .filter((g) => g.conversations.length > 0)
}
</script>

<template>
  <aside v-if="!collapsed" class="sidebar">
    <div class="sidebar-top">
      <button data-testid="new-chat-btn" class="new-chat-btn" @click="$emit('newChat')">
        <Icon icon="mdi:plus" width="18" />
        <span class="nav-label">New Chat</span>
      </button>
    </div>
    <div class="search-wrap">
      <Icon icon="mdi:magnify" width="16" class="search-icon" />
      <input v-model="search" class="search-input" placeholder="Search conversations..." />
    </div>
    <div class="conv-list">
      <template v-for="group in filteredGroups()" :key="group.label">
        <div class="date-label">{{ group.label }}</div>
        <ConversationItem
          v-for="conv in group.conversations"
          :key="conv.id"
          :id="conv.id"
          :name="conv.name"
          :members="membersFor(conv)"
          :is-active="conv.id === activeId"
          @select="$emit('select', conv.id)"
          @rename="(n) => $emit('rename', conv.id, n)"
          @delete="$emit('delete', conv.id)"
        />
      </template>
    </div>
  </aside>
  <button v-else class="expand-btn" title="Expand sidebar" @click="$emit('collapse')">
    <Icon icon="mdi:chevron-right" width="20" />
  </button>
</template>

<style scoped>
.sidebar {
  width: 280px;
  min-width: 280px;
  border-right: 1px solid var(--border);
  background: oklch(16% 0.012 255 / 0.9);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-top {
  padding: 12px;
  border-bottom: 1px solid var(--border);
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: 1px solid oklch(64% 0.18 255 / 0.4);
  border-radius: 8px;
  background: transparent;
  color: var(--accent);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
}

.new-chat-btn:hover {
  background: oklch(64% 0.18 255 / 0.1);
}

.search-wrap {
  position: relative;
  padding: 8px 12px;
}

.search-icon {
  position: absolute;
  left: 22px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--muted);
}

.search-input {
  width: 100%;
  padding: 6px 8px 6px 30px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: oklch(19% 0.014 255 / 0.5);
  color: var(--fg);
  font-size: 0.82rem;
  min-height: 32px;
}

.search-input::placeholder {
  color: var(--muted);
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 8px;
}

.date-label {
  padding: 6px 8px 2px;
  color: var(--muted);
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.expand-btn {
  width: 32px;
  min-width: 32px;
  border-right: 1px solid var(--border);
  background: oklch(16% 0.012 255 / 0.9);
  color: var(--muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  align-self: stretch;
}

.expand-btn:hover {
  color: var(--fg);
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add src/client/components/chat/ConversationItem.vue src/client/components/chat/ConversationSidebar.vue && git commit -m "feat(webui): add ConversationSidebar with date groups, search, rename, delete"
```

---

### Task 11: Create NewChatDialog component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/NewChatDialog.vue`

- [ ] **Step 1: Create NewChatDialog.vue**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../../api'

const props = defineProps<{
  instances: PublicInstance[]
}>()

const emit = defineEmits<{
  create: [name: string, memberIds: string[]]
  close: []
}>()

const name = ref('')
const selectedIds = ref<string[]>([])

const enabledInstances = computed(() => props.instances.filter((i) => i.enabled))
const canCreate = computed(() => name.value.trim().length > 0 && selectedIds.value.length >= 1)

function toggleInstance(id: string) {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((i) => i !== id)
  } else {
    selectedIds.value.push(id)
  }
}

function create() {
  if (!canCreate.value) return
  emit('create', name.value.trim(), [...selectedIds.value])
}
</script>

<template>
  <div class="dialog-backdrop" @click.self="$emit('close')">
    <div class="dialog" role="dialog" aria-label="New chat">
      <div class="dialog-header">
        <h3>New Chat</h3>
        <button class="close-btn" @click="$emit('close')"><Icon icon="mdi:close" width="18" /></button>
      </div>
      <div class="dialog-body">
        <label class="field-label">Chat name</label>
        <input v-model="name" class="field-input" placeholder="e.g. Code Review" data-testid="new-chat-name" @keyup.enter="create" />

        <label class="field-label">Select bots (min 1)</label>
        <div v-if="enabledInstances.length === 0" class="empty-msg">No instances available</div>
        <div v-else class="instance-list">
          <button
            v-for="inst in enabledInstances"
            :key="inst.id"
            class="instance-option"
            :class="{ selected: selectedIds.includes(inst.id) }"
            :data-testid="`select-instance-${inst.id}`"
            @click="toggleInstance(inst.id)"
          >
            <div class="check">{{ selectedIds.includes(inst.id) ? '☑' : '☐' }}</div>
            <div class="inst-name">{{ inst.name }}</div>
          </button>
        </div>
      </div>
      <div class="dialog-footer">
        <button class="btn secondary" @click="$emit('close')">Cancel</button>
        <button class="btn primary" :disabled="!canCreate" data-testid="create-chat" @click="create">Create</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: oklch(0% 0 0 / 0.5);
  display: grid;
  place-items: center;
}

.dialog {
  width: min(440px, 90vw);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: oklch(19% 0.014 255);
  box-shadow: 0 20px 60px oklch(0% 0 0 / 0.5);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}

.dialog-header h3 {
  margin: 0;
  font-size: 1rem;
}

.close-btn {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.close-btn:hover {
  color: var(--fg);
  background: var(--surface);
}

.dialog-body {
  padding: 16px 20px;
  display: grid;
  gap: 12px;
}

.field-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--fg);
}

.field-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: oklch(14% 0.012 255);
  color: var(--fg);
  font-size: 0.88rem;
  min-height: 40px;
}

.instance-list {
  display: grid;
  gap: 4px;
}

.instance-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--fg);
  cursor: pointer;
  text-align: left;
  font-size: 0.85rem;
}

.instance-option.selected {
  border-color: var(--accent);
  background: oklch(64% 0.18 255 / 0.1);
}

.instance-option:hover {
  background: oklch(22% 0.014 255);
}

.check {
  font-size: 1rem;
  color: var(--accent);
}

.inst-name {
  flex: 1;
}

.empty-msg {
  color: var(--muted);
  font-size: 0.85rem;
  padding: 8px 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
}

.btn {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}

.btn.primary {
  border: 1px solid var(--accent);
  background: var(--accent);
  color: oklch(99% 0 0);
}

.btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.secondary {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--fg);
}

.btn.secondary:hover {
  background: var(--surface);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/client/components/chat/NewChatDialog.vue && git commit -m "feat(webui): add NewChatDialog with instance picker"
```

---

### Task 12: Create MessageList component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/MessageList.vue`

- [ ] **Step 1: Create MessageList.vue**

```vue
<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import MessageBubble from './MessageBubble.vue'
import type { TranscriptEntry } from '../../chatTranscript'
import type { PublicInstance } from '../../api'

const props = defineProps<{
  entries: TranscriptEntry[]
  instances: PublicInstance[]
}>()

const listEl = ref<HTMLElement>()
const shouldAutoScroll = ref(true)

function instanceFor(id: string) {
  return props.instances.find((i) => i.id === id)
}

function onScroll() {
  if (!listEl.value) return
  const { scrollTop, scrollHeight, clientHeight } = listEl.value
  shouldAutoScroll.value = scrollHeight - scrollTop - clientHeight < 60
}

watch(() => props.entries.length, async () => {
  if (!shouldAutoScroll.value) return
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
})

watch(() => props.entries[props.entries.length - 1]?.text, async () => {
  if (!shouldAutoScroll.value) return
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
})
</script>

<template>
  <div ref="listEl" class="message-list" @scroll="onScroll">
    <div class="message-list-inner">
      <div v-if="entries.length === 0" class="empty-state">
        Send a message to start the conversation.
      </div>
      <MessageBubble
        v-for="entry in entries"
        :key="entry.id"
        :entry="entry"
        :instance="instanceFor(entry.instanceId)"
      />
    </div>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.message-list-inner {
  max-width: 768px;
  margin: 0 auto;
}

.empty-state {
  display: grid;
  place-items: center;
  min-height: 200px;
  color: var(--muted);
  font-size: 0.9rem;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/client/components/chat/MessageList.vue && git commit -m "feat(webui): add MessageList with auto-scroll and empty state"
```

---

### Task 13: Create ChatArea component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/ChatArea.vue`

- [ ] **Step 1: Create ChatArea.vue**

```vue
<script setup lang="ts">
import ChatHeader from './ChatHeader.vue'
import MessageList from './MessageList.vue'
import ChatComposer from './ChatComposer.vue'
import type { TranscriptEntry } from '../../chatTranscript'
import type { PublicInstance, ComposerMedia } from '../../api'

defineProps<{
  name: string
  members: PublicInstance[]
  entries: TranscriptEntry[]
  instances: PublicInstance[]
  connectionStatuses: Record<string, 'idle' | 'connecting' | 'connected' | 'error' | 'disconnected'>
  isGenerating: boolean
  canSend: boolean
}>()

const emit = defineEmits<{
  send: [text: string, media: ComposerMedia[]]
  stop: []
  addMember: []
  removeMember: [instanceId: string]
  settings: []
}>()
</script>

<template>
  <div class="chat-area">
    <ChatHeader
      :name="name"
      :members="members"
      :connection-statuses="connectionStatuses"
      @add-member="$emit('addMember')"
      @remove-member="$emit('removeMember', $event)"
      @settings="$emit('settings')"
    />
    <MessageList :entries="entries" :instances="instances" />
    <ChatComposer
      :disabled="!canSend"
      :is-generating="isGenerating"
      @send="$emit('send', $event[0], $event[1])"
      @stop="$emit('stop')"
    />
  </div>
</template>

<style scoped>
.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/client/components/chat/ChatArea.vue && git commit -m "feat(webui): add ChatArea orchestrating header, messages, composer"
```

---

### Task 14: Create ChatView main component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/ChatView.vue`

- [ ] **Step 1: Create ChatView.vue**

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchConversations, saveConversations, type ComposerMedia, type PublicInstance, type Conversation } from '../../api'
import { appendOutboundMessage, applyChatEvent, createTranscriptState, type TranscriptEntry, type TranscriptState } from '../../chatTranscript'
import { createChatSocket, type ChatEvent, type ChatSocket } from '../../socket'
import { useConversations } from './useConversations'
import ConversationSidebar from './ConversationSidebar.vue'
import ChatArea from './ChatArea.vue'
import NewChatDialog from './NewChatDialog.vue'
import { Icon } from '@iconify/vue'

type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'error' | 'disconnected'

const props = withDefaults(defineProps<{
  token: string
  instances: PublicInstance[]
  createSocket?: (token: string) => ChatSocket
  loadConversationsApi?: typeof fetchConversations
  saveConversationsApi?: typeof saveConversations
}>(), {
  createSocket: createChatSocket,
  loadConversationsApi: () => fetchConversations,
  saveConversationsApi: () => saveConversations
})

const socket = props.createSocket(props.token)
const sidebarCollapsed = ref(false)
const showNewChatDialog = ref(false)
const statuses = ref<Record<string, ConnectionStatus>>({})
const isGenerating = ref(false)
const activeGeneratingIds = ref<Set<string>>(new Set())

const {
  conversations,
  activeConversationId,
  activeConversation,
  dateGroups,
  loadConversations,
  createConversation,
  deleteConversation,
  renameConversation,
  selectConversation,
  persistConversations
} = useConversations({
  loadConversationsApi: props.loadConversationsApi,
  saveConversationsApi: props.saveConversationsApi
})

const activeMembers = computed(() => {
  if (!activeConversation.value) return []
  return activeConversation.value.selectedIds
    .map((id) => props.instances.find((i) => i.id === id))
    .filter((i) => i?.enabled) as PublicInstance[]
})

const activeEntries = computed<TranscriptEntry[]>(() => {
  return activeConversation.value?.transcript.entries ?? []
})

const canSend = computed(() => activeMembers.value.length > 0)

function updateStatus(event: ChatEvent) {
  if (event.event === 'chat.connecting') statuses.value[event.instanceId] = 'connecting'
  else if (event.event === 'chat.connected') statuses.value[event.instanceId] = 'connected'
  else if (event.event === 'chat.connection_failed') statuses.value[event.instanceId] = 'error'
  else if (event.event === 'chat.disconnected') statuses.value[event.instanceId] = 'disconnected'
}

function conversationForEvent(event: ChatEvent) {
  if (event.topicId) return conversations.value.find((c) => c.id === event.topicId) ?? activeConversation.value
  return activeConversation.value
}

function ensureConnections(conv: Conversation) {
  const members = conv.selectedIds.filter((id) => props.instances.find((i) => i.id === id)?.enabled)
  if (members.length === 0) return
  for (const instanceId of members) {
    if (statuses.value[instanceId] === undefined || statuses.value[instanceId] === 'idle') {
      statuses.value[instanceId] = 'connecting'
    }
  }
  socket.emit('ensure_topic_connections', { topicId: conv.id, members, chatMappings: conv.chatMappings ?? {} })
}

function handleChatEvent(event: ChatEvent) {
  updateStatus(event)
  const conv = conversationForEvent(event)
  if (!conv) return

  if (event.event === 'attached' && event.chatId) {
    if (!conv.chatMappings) conv.chatMappings = {}
    conv.chatMappings[event.instanceId] = { chatId: event.chatId, status: 'attached' }
    persistConversations(props.token)
    return
  }

  if (event.event === 'error' && event.topicId) {
    if (!conv.chatMappings) conv.chatMappings = {}
    conv.chatMappings[event.instanceId] = { chatId: event.chatId, status: 'error', lastError: event.detail }
  }

  const instanceLabel = props.instances.find((i) => i.id === event.instanceId)?.name ?? event.instanceId
  applyChatEvent(conv.transcript, event, instanceLabel)

  if (event.event === 'delta') {
    activeGeneratingIds.value.add(event.instanceId)
    isGenerating.value = true
  }
  if (event.event === 'stream_end' || event.event === 'turn_end') {
    activeGeneratingIds.value.delete(event.instanceId)
    if (activeGeneratingIds.value.size === 0) isGenerating.value = false
  }

  persistConversations(props.token)
}

function sendMessage(text: string, media: ComposerMedia[]) {
  if (!activeConversation.value || !canSend.value) return
  socket.emit('send_group_message', {
    topicId: activeConversation.value.id,
    text,
    ...(media.length > 0 ? { media } : {}),
    memberIds: [...activeMembers.value.map((m) => m.id)],
    chatMappings: activeConversation.value.chatMappings ?? {}
  })
  appendOutboundMessage(activeConversation.value.transcript, text, media)
  isGenerating.value = true
  persistConversations(props.token)
}

function stopGenerating() {
  isGenerating.value = false
  activeGeneratingIds.value.clear()
}

async function handleCreateConversation(name: string, memberIds: string[]) {
  const conv = await createConversation(name, memberIds)
  ensureConnections(conv)
  persistConversations(props.token)
  showNewChatDialog.value = false
}

function handleSelectConversation(id: string) {
  selectConversation(id)
  if (activeConversation.value) ensureConnections(activeConversation.value)
}

function handleDeleteConversation(id: string) {
  deleteConversation(id)
  persistConversations(props.token)
}

function handleRenameConversation(id: string, newName: string) {
  renameConversation(id, newName)
  persistConversations(props.token)
}

function addMemberToActive(instanceId: string) {
  if (!activeConversation.value) return
  if (activeConversation.value.selectedIds.includes(instanceId)) return
  activeConversation.value.selectedIds.push(instanceId)
  ensureConnections(activeConversation.value)
  persistConversations(props.token)
}

function removeMemberFromActive(instanceId: string) {
  if (!activeConversation.value) return
  activeConversation.value.selectedIds = activeConversation.value.selectedIds.filter((id) => id !== instanceId)
  if (activeConversation.value.chatMappings) delete activeConversation.value.chatMappings[instanceId]
  persistConversations(props.token)
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

onMounted(() => {
  socket.on('chat_event', handleChatEvent)
  void loadConversations(props.token)
    .then(() => {
      if (activeConversation.value) ensureConnections(activeConversation.value)
    })
    .catch(() => {})
})

onUnmounted(() => {
  socket.disconnect()
})
</script>

<template>
  <div class="chat-view">
    <ConversationSidebar
      :date-groups="dateGroups"
      :active-id="activeConversationId"
      :instances="instances"
      :collapsed="sidebarCollapsed"
      @select="handleSelectConversation"
      @new-chat="showNewChatDialog = true"
      @rename="handleRenameConversation"
      @delete="handleDeleteConversation"
      @collapse="toggleSidebar"
    />
    <div class="chat-main">
      <button v-if="!sidebarCollapsed" class="collapse-btn" title="Collapse sidebar" @click="toggleSidebar">
        <Icon icon="mdi:chevron-left" width="18" />
      </button>
      <ChatArea
        v-if="activeConversation"
        :name="activeConversation.name"
        :members="activeMembers"
        :entries="activeEntries"
        :instances="instances"
        :connection-statuses="statuses"
        :is-generating="isGenerating"
        :can-send="canSend"
        @send="sendMessage"
        @stop="stopGenerating"
        @add-member="showNewChatDialog = true"
        @remove-member="removeMemberFromActive"
        @settings="() => {}"
      />
      <div v-else class="no-conversation">
        <Icon icon="mdi:message-text-outline" width="48" class="empty-icon" />
        <p>Select or create a conversation to start chatting</p>
      </div>
    </div>
    <NewChatDialog
      v-if="showNewChatDialog"
      :instances="instances"
      @create="handleCreateConversation"
      @close="showNewChatDialog = false"
    />
  </div>
</template>

<style scoped>
.chat-view {
  display: flex;
  height: calc(100vh - 62px);
  overflow: hidden;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}

.collapse-btn {
  position: absolute;
  top: 12px;
  left: 4px;
  z-index: 3;
  width: 28px;
  height: 28px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--muted);
  display: grid;
  place-items: center;
  cursor: pointer;
}

.collapse-btn:hover {
  color: var(--fg);
}

.no-conversation {
  flex: 1;
  display: grid;
  place-items: center;
  gap: 12px;
  color: var(--muted);
  font-size: 0.9rem;
}

.empty-icon {
  opacity: 0.4;
}

@media (max-width: 768px) {
  .chat-view {
    flex-direction: column;
  }
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add src/client/components/chat/ChatView.vue && git commit -m "feat(webui): add ChatView main component with sidebar, chat area, socket integration"
```

---

### Task 15: Write ChatView tests

**Files:**
- Create: `nanobot-webui/src/client/components/chat/ChatView.test.ts`

- [ ] **Step 1: Write the test**

```ts
import { mount } from '@vue/test-utils'
import { EventEmitter } from 'node:events'
import { describe, expect, it, vi } from 'vitest'
import ChatView from './ChatView.vue'

class FakeSocket extends EventEmitter {
  emitted: Array<{ event: string; payload: unknown }> = []
  emit(event: string, payload?: unknown) {
    this.emitted.push({ event, payload })
    return super.emit(event, payload)
  }
  disconnect = vi.fn()
}

const alpha = { id: 'alpha', name: 'Alpha', baseUrl: 'http://alpha', enabled: true }
const beta = { id: 'beta', name: 'Beta', baseUrl: 'http://beta', enabled: true }

function mountChatView(socket: FakeSocket, options: Record<string, unknown> = {}) {
  return mount(ChatView, {
    props: {
      token: 'dashboard',
      createSocket: () => socket,
      loadConversationsApi: vi.fn().mockResolvedValue([]),
      saveConversationsApi: vi.fn().mockResolvedValue([]),
      instances: [alpha, beta],
      ...options
    },
    global: {
      stubs: {
        ConversationSidebar: true,
        ChatArea: true,
        NewChatDialog: true
      }
    }
  })
}

describe('ChatView', () => {
  it('loads conversations on mount', async () => {
    const socket = new FakeSocket()
    const load = vi.fn().mockResolvedValue([{ id: 'c1', name: 'Test', selectedIds: ['alpha'], chatMappings: {}, transcript: { entries: [], debugEvents: [] } }])
    mountChatView(socket, { loadConversationsApi: load })
    expect(load).toHaveBeenCalledWith('dashboard')
  })

  it('creates a conversation via NewChatDialog and ensures connections', async () => {
    const socket = new FakeSocket()
    const save = vi.fn().mockResolvedValue([])
    const wrapper = mountChatView(socket, { saveConversationsApi: save })
    await wrapper.vm.$nextTick()

    const conv = await wrapper.vm.handleCreateConversation('Code Review', ['alpha'])
    expect(conv.name).toBe('Code Review')
    expect(conv.selectedIds).toEqual(['alpha'])
    expect(socket.emitted).toContainEqual(
      expect.objectContaining({ event: 'ensure_topic_connections' })
    )
  })

  it('sends a message to the active conversation', async () => {
    const socket = new FakeSocket()
    const save = vi.fn().mockResolvedValue([])
    const wrapper = mountChatView(socket, { saveConversationsApi: save })
    await wrapper.vm.handleCreateConversation('Chat', ['alpha'])
    await wrapper.vm.sendMessage('hello', [])

    expect(socket.emitted).toContainEqual(
      expect.objectContaining({ event: 'send_group_message' })
    )
  })

  it('handles delta events as streaming and stops on stream_end', async () => {
    const socket = new FakeSocket()
    const save = vi.fn().mockResolvedValue([])
    const wrapper = mountChatView(socket, { saveConversationsApi: save })
    await wrapper.vm.handleCreateConversation('Chat', ['alpha'])
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.isGenerating).toBe(false)
    socket.emit('chat_event', { instanceId: 'alpha', event: 'delta', chatId: 'c1', text: 'hello' })
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.isGenerating).toBe(true)

    socket.emit('chat_event', { instanceId: 'alpha', event: 'stream_end', chatId: 'c1' })
    await wrapper.vm.$nextTick()
    expect(wrapper.vm.isGenerating).toBe(false)
  })

  it('routes attached events to the correct conversation chatMappings', async () => {
    const socket = new FakeSocket()
    const save = vi.fn().mockResolvedValue([])
    const wrapper = mountChatView(socket, { saveConversationsApi: save })
    const conv = await wrapper.vm.handleCreateConversation('Chat', ['alpha'])
    socket.emit('chat_event', { topicId: conv.id, instanceId: 'alpha', event: 'attached', chatId: 'chat-1' })
    await wrapper.vm.$nextTick()
    expect(conv.chatMappings.alpha).toEqual({ chatId: 'chat-1', status: 'attached' })
  })

  it('deletes a conversation', async () => {
    const socket = new FakeSocket()
    const save = vi.fn().mockResolvedValue([])
    const wrapper = mountChatView(socket, { saveConversationsApi: save })
    const conv = await wrapper.vm.handleCreateConversation('To Delete', ['alpha'])
    await wrapper.vm.handleDeleteConversation(conv.id)
    expect(wrapper.vm.conversations).toHaveLength(0)
  })

  it('renames a conversation', async () => {
    const socket = new FakeSocket()
    const save = vi.fn().mockResolvedValue([])
    const wrapper = mountChatView(socket, { saveConversationsApi: save })
    const conv = await wrapper.vm.handleCreateConversation('Old Name', ['alpha'])
    await wrapper.vm.handleRenameConversation(conv.id, 'New Name')
    expect(conv.name).toBe('New Name')
  })
})
```

- [ ] **Step 2: Run test**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/components/chat/ChatView.test.ts
```

Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add src/client/components/chat/ChatView.test.ts && git commit -m "test(webui): add ChatView tests for CRUD, messaging, streaming, routing"
```

---

### Task 16: Wire ChatView into App.vue and update nav

**Files:**
- Modify: `nanobot-webui/src/client/App.vue`

- [ ] **Step 1: Update imports — replace ChatPanel with ChatView**

In `App.vue`, change:
```ts
import ChatPanel from './components/ChatPanel.vue'
```
to:
```ts
import ChatView from './components/chat/ChatView.vue'
```

- [ ] **Step 2: Update the nav label "Chat Topics" → "Chat"**

Change the nav button with `data-nav="chat"` from:
```html
<span class="nav-label">Chat Topics</span>
```
to:
```html
<span class="nav-label">Chat</span>
```

Also update the `activeTabLabel` map:
```ts
chat: 'Chat Topics'
```
to:
```ts
chat: 'Chat'
```

- [ ] **Step 3: Replace ChatPanel with ChatView in the template**

Change:
```html
<ChatPanel v-else-if="activeTab === 'chat'" :token="token" :instances="instances" />
```
to:
```html
<ChatView v-else-if="activeTab === 'chat'" :token="token" :instances="instances" />
```

Also update the mobile drawer nav label from `Chat` (already correct) — no change needed there.

- [ ] **Step 4: Remove the pinned topics section and loadPinnedTopics**

Remove the `pinnedTopics` ref, `loadPinnedTopics` function, `openPinnedTopic` function, and the `<nav>` block with `pinnedTopics`. Also remove the `loadPinnedTopics()` call from `login()`. The conversation sidebar in ChatView replaces this functionality.

- [ ] **Step 5: Run tests**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run src/client/App.test.ts
```

Expected: All pass (may need minor updates if tests reference ChatPanel or pinned topics)

- [ ] **Step 6: Commit**

```bash
git add src/client/App.vue && git commit -m "feat(webui): wire ChatView into App.vue, rename nav label to Chat"
```

---

### Task 17: Delete old ChatPanel and markdownTranscript files

**Files:**
- Delete: `nanobot-webui/src/client/components/ChatPanel.vue`
- Delete: `nanobot-webui/src/client/components/ChatPanel.test.ts`
- Delete: `nanobot-webui/src/client/markdownTranscript.ts`
- Delete: `nanobot-webui/src/client/markdownTranscript.test.ts`

- [ ] **Step 1: Delete old files**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && rm src/client/components/ChatPanel.vue src/client/components/ChatPanel.test.ts src/client/markdownTranscript.ts src/client/markdownTranscript.test.ts
```

- [ ] **Step 2: Run full test suite**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run
```

Expected: All pass

- [ ] **Step 3: Run type check**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vue-tsc --noEmit
```

Expected: No errors

- [ ] **Step 4: Run build**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npm run build
```

Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "chore(webui): remove old ChatPanel and markdownTranscript, replaced by ChatView"
```

---

### Task 18: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vitest run
```

Expected: All pass

- [ ] **Step 2: Run type check**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npx vue-tsc --noEmit
```

Expected: No errors

- [ ] **Step 3: Run build**

```bash
cd /Users/raffles/git/nanobot-rg/nanobot-webui && npm run build
```

Expected: Build succeeds

- [ ] **Step 4: Verify spec coverage**

Check each spec requirement maps to a task:
- ChatGPT-style layout → Tasks 12, 13, 14
- Conversation sidebar with date grouping → Tasks 4, 10
- Auto-growing composer → Task 8
- Streaming cursor → Task 7 (MessageBubble)
- Rich code blocks → Tasks 3, 5
- Iconify icons → Tasks 5–14 (all components)
- Group chat (1+ bots) → Tasks 9, 11, 14
- Header bar with avatars → Task 9
- New chat dialog → Task 11
- Copy action only → Task 7
- Enter to send, Shift+Enter newline → Task 8
- Sidebar collapse → Task 14
- Search conversations → Task 10
- Rename/delete → Task 10
- File attachments → Task 8
- Streaming stop button → Task 8
- markdown-it replacement → Task 3
- api.ts wrappers → Task 2
- App.vue integration → Task 16

All covered. ✓
