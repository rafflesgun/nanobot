# @ Mention Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `@AgentName` and `@all` mention support with autocomplete dropdown, routing logic, and visual highlighting.

**Architecture:** Plain-text `@Name` tokens in the existing textarea (no contenteditable). A `parseMentions()` utility extracts mentions and resolves routing. A floating dropdown in ChatComposer provides autocomplete. MessageBubble highlights `@Name` patterns post-render.

**Tech Stack:** Vue 3, TypeScript, @iconify/vue, vitest

---

### Task 1: parseMentions utility

**Files:**
- Create: `nanobot-webui/src/client/mentionUtils.ts`
- Create: `nanobot-webui/src/client/mentionUtils.test.ts`

- [ ] **Step 1: Write failing tests for parseMentions**

```typescript
// mentionUtils.test.ts
import { describe, expect, it } from 'vitest'
import { parseMentions, extractMentionQuery, isMentionTrigger } from './mentionUtils'
import type { PublicInstance } from './api'

const members: PublicInstance[] = [
  { id: 'a1', name: 'Alpha', baseUrl: '', enabled: true },
  { id: 'b2', name: 'Beta', baseUrl: '', enabled: true },
  { id: 'g3', name: 'Gamma', baseUrl: '', enabled: true },
]

describe('parseMentions', () => {
  it('returns empty mentionedIds when no @mentions in text', () => {
    const result = parseMentions('hello world', members)
    expect(result.mentionedIds).toEqual([])
  })

  it('matches single @mention by name (case-insensitive)', () => {
    const result = parseMentions('@alpha how are you?', members)
    expect(result.mentionedIds).toEqual(['a1'])
  })

  it('matches multiple @mentions', () => {
    const result = parseMentions('@Alpha @Beta please collaborate', members)
    expect(result.mentionedIds).toEqual(['a1', 'b2'])
  })

  it('resolves @all to all member IDs', () => {
    const result = parseMentions('@all team update', members)
    expect(result.mentionedIds).toEqual(['a1', 'b2', 'g3'])
  })

  it('@all wins over individual mentions', () => {
    const result = parseMentions('@Alpha @all hi', members)
    expect(result.mentionedIds).toEqual(['a1', 'b2', 'g3'])
  })

  it('ignores @mention of non-member', () => {
    const result = parseMentions('@Unknown hello', members)
    expect(result.mentionedIds).toEqual([])
  })

  it('does not match mid-word @', () => {
    const result = parseMentions('email@domain.com', members)
    expect(result.mentionedIds).toEqual([])
  })

  it('deduplicates mentioned IDs', () => {
    const result = parseMentions('@Alpha @Alpha again', members)
    expect(result.mentionedIds).toEqual(['a1'])
  })

  it('returns text unchanged', () => {
    const text = '@Alpha check this out'
    const result = parseMentions(text, members)
    expect(result.text).toBe(text)
  })
})

describe('isMentionTrigger', () => {
  it('returns true for @ at position 0', () => {
    expect(isMentionTrigger('@', 0, '')).toBe(true)
  })

  it('returns true for @ after space', () => {
    expect(isMentionTrigger('hello @', 6, 'hello ')).toBe(true)
  })

  it('returns true for @ after newline', () => {
    expect(isMentionTrigger('hello\n@', 6, 'hello\n')).toBe(true)
  })

  it('returns false for mid-word @', () => {
    expect(isMentionTrigger('email@', 5, 'email')).toBe(false)
  })
})

describe('extractMentionQuery', () => {
  it('extracts query after @ at end of text', () => {
    expect(extractMentionQuery('hello @al', 9)).toEqual({ query: 'al', startIndex: 6 })
  })

  it('extracts query after @ with trailing content', () => {
    expect(extractMentionQuery('hello @al world', 9)).toEqual({ query: 'al', startIndex: 6 })
  })

  it('returns null when cursor is not after @mention', () => {
    expect(extractMentionQuery('hello world', 5)).toBeNull()
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/client/mentionUtils.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Write implementation**

```typescript
// mentionUtils.ts
import type { PublicInstance } from './api'

export type MentionResult = {
  mentionedIds: string[]
  text: string
}

export function parseMentions(text: string, members: PublicInstance[]): MentionResult {
  const tokens = text.match(/(?<=^|[\s])@(\w+)/g)
  if (!tokens) return { mentionedIds: [], text }
  const seen = new Set<string>()
  const ids: string[] = []
  let hasAll = false
  for (const token of tokens) {
    const name = token.slice(1)
    if (name.toLowerCase() === 'all') {
      hasAll = true
    }
  }
  if (hasAll) {
    for (const m of members) {
      if (!seen.has(m.id)) { seen.add(m.id); ids.push(m.id) }
    }
    return { mentionedIds: ids, text }
  }
  for (const token of tokens) {
    const name = token.slice(1)
    const match = members.find(m => m.name.toLowerCase() === name.toLowerCase())
    if (match && !seen.has(match.id)) { seen.add(match.id); ids.push(match.id) }
  }
  return { mentionedIds: ids, text }
}

export function isMentionTrigger(text: string, cursorPos: number, _before: string): boolean {
  if (cursorPos <= 0) return false
  if (text[cursorPos - 1] !== '@') return false
  if (cursorPos === 1) return true
  const before = text[cursorPos - 2]
  return before === ' ' || before === '\n' || before === '\t'
}

export function extractMentionQuery(text: string, cursorPos: number): { query: string; startIndex: number } | null {
  let i = cursorPos - 1
  while (i >= 0 && text[i] !== '@') i--
  if (i < 0) return null
  if (i > 0 && text[i - 1] !== ' ' && text[i - 1] !== '\n' && text[i - 1] !== '\t') return null
  const query = text.slice(i + 1, cursorPos)
  return { query, startIndex: i }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/client/mentionUtils.test.ts`
Expected: 12 tests PASS

- [ ] **Step 5: Commit**

```bash
git add nanobot-webui/src/client/mentionUtils.ts nanobot-webui/src/client/mentionUtils.test.ts
git commit -m "feat(webui): add parseMentions utility with tests"
```

---

### Task 2: MentionDropdown component

**Files:**
- Create: `nanobot-webui/src/client/components/chat/MentionDropdown.vue`

- [ ] **Step 1: Write MentionDropdown component**

```vue
<!-- MentionDropdown.vue -->
<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { PublicInstance } from '../../api'

type MentionItem = {
  id: string
  name: string
  isAll: boolean
  status?: string
}

const props = defineProps<{
  members: PublicInstance[]
  connectionStatuses: Record<string, string>
  query: string
  visible: boolean
}>()

const emit = defineEmits<{
  select: [item: MentionItem]
  close: []
}>()

const highlightedIndex = ref(0)

const items = computed<MentionItem[]>(() => {
  const result: MentionItem[] = []
  if (props.members.length >= 2) {
    const allMatch = 'all'.includes(props.query.toLowerCase())
    if (allMatch) result.push({ id: '__all__', name: 'all', isAll: true })
  }
  const filtered = props.members.filter(m =>
    m.name.toLowerCase().includes(props.query.toLowerCase())
  )
  for (const m of filtered) {
    result.push({ id: m.id, name: m.name, isAll: false, status: props.connectionStatuses[m.id] })
  }
  return result
})

watch(() => props.query, () => {
  highlightedIndex.value = 0
})

function statusColor(status?: string): string {
  if (status === 'connected') return '#4a7'
  if (status === 'connecting') return '#da3'
  if (status === 'error' || status === 'disconnected') return '#d55'
  return '#666'
}

function avatarColor(name: string): string {
  const colors = ['#5a5aff', '#4a7', '#da3', '#d5a', '#7ad', '#a77']
  let sum = 0
  for (let i = 0; i < name.length; i++) sum += name.charCodeAt(i)
  return colors[sum % colors.length]
}

function moveUp() {
  if (items.value.length === 0) return
  highlightedIndex.value = (highlightedIndex.value - 1 + items.value.length) % items.value.length
}

function moveDown() {
  if (items.value.length === 0) return
  highlightedIndex.value = (highlightedIndex.value + 1) % items.value.length
}

function confirm() {
  const item = items.value[highlightedIndex.value]
  if (item) emit('select', item)
}

defineExpose({ moveUp, moveDown, confirm, items, highlightedIndex })
</script>

<template>
  <div v-if="visible && items.length > 0" class="mention-dropdown">
    <div
      v-for="(item, i) in items"
      :key="item.id"
      class="mention-item"
      :class="{ highlighted: i === highlightedIndex }"
      @click="emit('select', item)"
      @mouseenter="highlightedIndex = i"
    >
      <div v-if="item.isAll" class="mention-avatar all-avatar">
        <Icon icon="mdi:account-group-outline" :width="14" />
      </div>
      <div v-else class="mention-avatar" :style="{ background: avatarColor(item.name) }">
        {{ item.name.charAt(0).toUpperCase() }}
      </div>
      <span class="mention-name">@{{ item.name }}</span>
      <span v-if="item.isAll" class="mention-label">all members</span>
      <span v-else class="mention-status" :style="{ background: statusColor(item.status) }" />
    </div>
  </div>
  <div v-else-if="visible && items.length === 0" class="mention-dropdown empty">
    <span class="no-results">No matching agents</span>
  </div>
</template>

<style scoped>
.mention-dropdown {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  background: oklch(20% 0.014 255);
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 4px;
  max-height: 240px;
  overflow-y: auto;
  z-index: 50;
  box-shadow: 0 -4px 16px oklch(0% 0 0 / 0.4);
}

.mention-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  cursor: pointer;
  transition: background 80ms;
}

.mention-item:first-child {
  border-radius: 10px 10px 0 0;
}

.mention-item:last-child {
  border-radius: 0 0 10px 10px;
}

.mention-item.highlighted {
  background: oklch(30% 0.02 255);
}

.mention-avatar {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
}

.all-avatar {
  background: oklch(50% 0.12 255);
}

.mention-name {
  font-size: 0.82rem;
  font-weight: 500;
}

.mention-label {
  font-size: 0.72rem;
  color: var(--muted);
  margin-left: auto;
}

.mention-status {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-left: auto;
  flex-shrink: 0;
}

.empty {
  padding: 10px 14px;
}

.no-results {
  font-size: 0.78rem;
  color: var(--muted);
}
</style>
```

- [ ] **Step 2: Verify component compiles**

Run: `npx vue-tsc --noEmit`
Expected: no errors

- [ ] **Step 3: Commit**

```bash
git add nanobot-webui/src/client/components/chat/MentionDropdown.vue
git commit -m "feat(webui): add MentionDropdown component"
```

---

### Task 3: Integrate dropdown into ChatComposer

**Files:**
- Modify: `nanobot-webui/src/client/components/chat/ChatComposer.vue`
- Modify: `nanobot-webui/src/client/components/chat/ChatArea.vue`

- [ ] **Step 1: Update ChatComposer props, state, and event handling**

Add `members` and `connectionStatuses` props. Add mention dropdown state. Update `handleKeydown` for dropdown keyboard nav. Update `handleInput` for `@` trigger detection. Update `send` to emit mention info.

Key changes to `ChatComposer.vue` `<script setup>`:

```typescript
import { ref, watch, nextTick, computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { ComposerMedia, PublicInstance } from '../../api'
import { extractMentionQuery, isMentionTrigger } from '../../mentionUtils'
import MentionDropdown from './MentionDropdown.vue'

type MentionItem = { id: string; name: string; isAll: boolean; status?: string }

const props = defineProps<{
  disabled: boolean
  isGenerating: boolean
  members: PublicInstance[]
  connectionStatuses: Record<string, string>
}>()

const emit = defineEmits<{
  send: [text: string, media: ComposerMedia[], mentionedIds: string[]]
  stop: []
}>()

const message = ref('')
const pendingAttachments = ref<ComposerMedia[]>([])
const textarea = ref<HTMLTextAreaElement | null>(null)
const dropdownRef = ref<InstanceType<typeof MentionDropdown> | null>(null)
const showMentionDropdown = ref(false)
const mentionQuery = ref('')
const mentionStartIndex = ref(-1)

const isMultiline = computed(() => message.value.includes('\n'))

watch(message, () => {
  nextTick(() => {
    const el = textarea.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 360) + 'px'
  })
})

function handleInput() {
  const el = textarea.value
  if (!el) return
  const pos = el.selectionStart
  const text = message.value
  if (isMentionTrigger(text, pos, text.slice(0, pos))) {
    showMentionDropdown.value = true
    mentionQuery.value = ''
    mentionStartIndex.value = pos - 1
    return
  }
  if (showMentionDropdown.value && mentionStartIndex.value >= 0) {
    const result = extractMentionQuery(text, pos)
    if (result && result.startIndex === mentionStartIndex.value) {
      mentionQuery.value = result.query
    } else {
      showMentionDropdown.value = false
    }
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (showMentionDropdown.value) {
    if (e.key === 'ArrowDown') { e.preventDefault(); dropdownRef.value?.moveDown(); return }
    if (e.key === 'ArrowUp') { e.preventDefault(); dropdownRef.value?.moveUp(); return }
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      if (dropdownRef.value && dropdownRef.value.items.length > 0) {
        dropdownRef.value.confirm()
      }
      return
    }
    if (e.key === 'Escape') { e.preventDefault(); showMentionDropdown.value = false; return }
  }
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function selectMention(item: MentionItem) {
  const name = item.isAll ? 'all' : item.name
  const before = message.value.slice(0, mentionStartIndex.value)
  const after = message.value.slice(textarea.value?.selectionStart ?? message.value.length)
  message.value = `${before}@${name} ${after}`
  showMentionDropdown.value = false
  nextTick(() => {
    const el = textarea.value
    if (el) {
      const newPos = before.length + name.length + 2
      el.setSelectionRange(newPos, newPos)
      el.focus()
    }
  })
}

function send() {
  const text = message.value.trim()
  if (!text && pendingAttachments.value.length === 0) return
  if (props.disabled || props.isGenerating) return
  emit('send', text, [...pendingAttachments.value], [])
  message.value = ''
  pendingAttachments.value = []
  showMentionDropdown.value = false
  nextTick(() => {
    const el = textarea.value
    if (el) el.style.height = 'auto'
  })
}
```

- [ ] **Step 2: Update ChatComposer template**

Add `MentionDropdown` and `@input` handler. The composer-input wrapper needs `position: relative` and the dropdown positioned above. Add the mention hint for multi-agent conversations.

```vue
<template>
  <div class="composer">
    <div v-if="pendingAttachments.length" class="attachment-row">
      <span
        v-for="(att, i) in pendingAttachments"
        :key="i"
        class="attachment-chip"
        @click="removeAttachment(i)"
      >
        {{ att.name ?? 'attachment' }} ×
      </span>
    </div>
    <div class="composer-input-wrapper">
      <MentionDropdown
        ref="dropdownRef"
        :members="props.members"
        :connection-statuses="props.connectionStatuses"
        :query="mentionQuery"
        :visible="showMentionDropdown"
        @select="selectMention"
        @close="showMentionDropdown = false"
      />
      <div class="composer-input" :class="{ multiline: isMultiline }">
        <label class="attach-button">
          <Icon icon="mdi:plus-circle-outline" :width="22" />
          <input
            type="file"
            multiple
            data-testid="attachment-input"
            @change="onFileSelect"
          />
        </label>
        <textarea
          ref="textarea"
          v-model="message"
          class="chat-textarea"
          rows="1"
          :placeholder="disabled ? 'Add at least one bot to start chatting' : 'Message...'"
          :disabled="disabled"
          data-testid="chat-input"
          @keydown="handleKeydown"
          @input="handleInput"
          @paste="onPaste"
          @blur="onBlur"
        />
        <button
          v-if="isGenerating"
          class="send-button stop"
          data-testid="stop-button"
          @click="emit('stop')"
        >
          <Icon icon="mdi:stop-circle" :width="20" />
        </button>
        <button
          v-else
          class="send-button"
          :class="{ disabled: disabled || (!message.trim() && !pendingAttachments.length) }"
          data-testid="send-button"
          :disabled="disabled"
          @click="send"
        >
          <Icon icon="mdi:arrow-up" :width="18" />
        </button>
      </div>
    </div>
    <div v-if="showMentionHint" class="mention-hint">
      Mention @all or @AgentName to send
    </div>
  </div>
</template>
```

Add computed `showMentionHint`:

```typescript
const showMentionHint = computed(() => {
  if (props.members.length < 2) return false
  if (!message.value.trim()) return false
  const hasMention = /(?<=^|[\s])@(\w+)/.test(message.value)
  return !hasMention
})
```

Add `onBlur` with delay to allow click:

```typescript
function onBlur() {
  setTimeout(() => { showMentionDropdown.value = false }, 150)
}
```

- [ ] **Step 3: Update ChatComposer styles**

Add these styles:

```css
.composer-input-wrapper {
  position: relative;
}

.mention-hint {
  text-align: center;
  font-size: 0.72rem;
  color: var(--muted);
  padding: 4px 0 0;
  opacity: 0.7;
}
```

- [ ] **Step 4: Update ChatArea to pass members + connectionStatuses**

```vue
<ChatComposer
  :disabled="!props.canSend"
  :is-generating="props.isGenerating"
  :members="props.members"
  :connection-statuses="props.connectionStatuses"
  @send="(text: string, media: ComposerMedia[], mentionedIds: string[]) => emit('send', text, media, mentionedIds)"
  @stop="emit('stop')"
/>
```

Update `ChatArea.vue` emit type:

```typescript
const emit = defineEmits<{
  send: [text: string, media: ComposerMedia[], mentionedIds: string[]]
  stop: []
  addMember: []
  removeMember: [instanceId: string]
  toggleSidebar: []
}>()
```

- [ ] **Step 5: Verify types and build**

Run: `npx vue-tsc --noEmit && npm run build`
Expected: no errors, build succeeds

- [ ] **Step 6: Commit**

```bash
git add nanobot-webui/src/client/components/chat/ChatComposer.vue nanobot-webui/src/client/components/chat/ChatArea.vue
git commit -m "feat(webui): integrate @mention dropdown into ChatComposer"
```

---

### Task 4: Routing logic in ChatView

**Files:**
- Modify: `nanobot-webui/src/client/components/chat/ChatView.vue`

- [ ] **Step 1: Update sendMessage to use parseMentions**

Current `sendMessage` at line 192:

```typescript
function sendMessage(text: string, media: ComposerMedia[]) {
  if (!activeConversation.value) return
  socket.emit('send_group_message', {
    topicId: activeConversation.value.id,
    text,
    media: media.length > 0 ? media : undefined,
    memberIds: activeConversation.value.selectedIds,
    chatMappings: activeConversation.value.chatMappings ?? {},
  })
  appendOutboundMessage(activeConversation.value.transcript as TranscriptState, text, media)
  setGenerating(true)
  persistConversations(props.token)
}
```

Replace with:

```typescript
import { parseMentions } from '../../mentionUtils'

function sendMessage(text: string, media: ComposerMedia[], _mentionedIds: string[]) {
  if (!activeConversation.value) return
  const { mentionedIds } = parseMentions(text, activeMembers.value)
  const allMemberIds = activeConversation.value.selectedIds
  if (activeMembers.value.length >= 2 && mentionedIds.length === 0) return
  const memberIds = mentionedIds.length > 0 ? mentionedIds : allMemberIds
  socket.emit('send_group_message', {
    topicId: activeConversation.value.id,
    text,
    media: media.length > 0 ? media : undefined,
    memberIds,
    chatMappings: activeConversation.value.chatMappings ?? {},
  })
  appendOutboundMessage(activeConversation.value.transcript as TranscriptState, text, media)
  setGenerating(true)
  persistConversations(props.token)
}
```

- [ ] **Step 2: Update the ChatArea emit binding in the template**

In ChatView template, update:

```vue
@send="(text: string, media: ComposerMedia[], mentionedIds: string[]) => sendMessage(text, media, mentionedIds)"
```

- [ ] **Step 3: Verify types and build**

Run: `npx vue-tsc --noEmit && npm run build`
Expected: no errors

- [ ] **Step 4: Run all tests**

Run: `npx vitest run`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add nanobot-webui/src/client/components/chat/ChatView.vue
git commit -m "feat(webui): route messages by @mention with @all broadcast"
```

---

### Task 5: Highlight @mentions in MessageBubble

**Files:**
- Modify: `nanobot-webui/src/client/components/chat/MessageBubble.vue`

- [ ] **Step 1: Add mention highlighting to parsedBlocks**

In `MessageBubble.vue`, add a `highlightMentions` function that post-processes the HTML output from `renderMarkdown`. Insert before `parsedBlocks()`:

```typescript
const mentionNames = computed(() => {
  const names = ['all']
  for (const inst of (props.entry.instances ?? [])) names.push(inst.name)
  return names
})

function highlightMentions(html: string): string {
  return html.replace(/@(\w+)/g, (match, name) => {
    if (name.toLowerCase() === 'all' || mentionNames.value.some(n => n.toLowerCase() === name.toLowerCase())) {
      return `<span class="mention-tag">${match}</span>`
    }
    return match
  })
}
```

Update `parsedBlocks` to call `highlightMentions` on the rendered HTML:

```typescript
function parsedBlocks(): Array<{ type: 'html' | 'code'; content: string; language: string; rawCode: string }> {
  const html = highlightMentions(renderMarkdown(displayText()))
  // ... rest unchanged
}
```

Note: `mentionNames` needs instance data. Update the `entry` type to optionally carry instances. Simpler alternative: accept `instances` prop and build names from it. The `MessageBubble` already has an `instance` prop (single). For multi-agent, pass `instances` array.

Add prop:

```typescript
const props = defineProps<{
  entry: TranscriptEntry
  instance?: PublicInstance
  instances?: PublicInstance[]
}>()
```

Then update `mentionNames`:

```typescript
const mentionNames = computed(() => {
  const names = ['all']
  if (props.instances) {
    for (const inst of props.instances) names.push(inst.name)
  } else if (props.instance) {
    names.push(props.instance.name)
  }
  return names
})
```

- [ ] **Step 2: Add mention-tag styles**

```css
.mention-tag {
  background: oklch(64% 0.18 255 / 0.12);
  color: oklch(72% 0.14 250);
  padding: 0.1em 0.3em;
  border-radius: 4px;
  font-weight: 500;
}
```

- [ ] **Step 3: Pass instances prop from MessageList → MessageBubble**

In `MessageList.vue`, pass `instances` to each `MessageBubble`:

```vue
<MessageBubble
  :entry="entry"
  :instance="instances.find(i => i.id === entry.instanceId)"
  :instances="instances"
/>
```

(Check if `instances` is already a prop on MessageList — it is, passed from ChatArea.)

- [ ] **Step 4: Verify types and build**

Run: `npx vue-tsc --noEmit && npm run build`
Expected: no errors

- [ ] **Step 5: Commit**

```bash
git add nanobot-webui/src/client/components/chat/MessageBubble.vue nanobot-webui/src/client/components/chat/MessageList.vue
git commit -m "feat(webui): highlight @mentions in message bubbles"
```

---

### Task 6: Final verification

**Files:** none new

- [ ] **Step 1: Run full test suite**

Run: `npx vitest run`
Expected: all tests pass

- [ ] **Step 2: Typecheck and build**

Run: `npx vue-tsc --noEmit && npm run build`
Expected: clean

- [ ] **Step 3: Commit any lint fixes if needed**
