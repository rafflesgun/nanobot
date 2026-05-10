# Chat UI Redesign — ChatGPT-style with Group Chat

**Date:** 2026-05-10
**Status:** Approved
**Replaces:** `ChatPanel.vue` (topic-based two-column layout)

## Summary

Replace the current ChatPanel with a ChatGPT-style chat interface. One conversation per group (1+ bot instances), conversation sidebar with date grouping, auto-growing composer, streaming cursor, rich code blocks, and Iconify icons. Group chat semantics preserved — each conversation invites 1+ nanobot instances.

## Approach

**Full rewrite (Approach A).** Replace `ChatPanel.vue` entirely with `ChatView.vue`. Reuse `chatTranscript.ts` and `socket.ts` unchanged. Replace `markdownTranscript.ts` with `markdown-it`. Migrate topic model → conversation model in `api.ts`.

## Component Tree

```
ChatView.vue (replaces ChatPanel.vue)
├── ConversationSidebar.vue
│   ├── NewChatButton.vue
│   ├── ConversationSearch.vue
│   └── ConversationList.vue
│       └── ConversationItem.vue
├── ChatArea.vue
│   ├── ChatHeader.vue (title + member avatars + settings gear)
│   ├── MessageList.vue (scroll container, auto-scroll)
│   │   └── MessageBubble.vue (user or bot, with avatar)
│   │       └── CodeBlock.vue (syntax-highlighted, copy + download)
│   ├── ToolCallBlock.vue (collapsible tool invocation display)
│   └── ChatComposer.vue (auto-growing textarea + file attach + send)
└── NewChatDialog.vue (modal: pick instances, name the chat)
```

## Data Model

### Renamed types (`api.ts`)

- `StateTopic` → `Conversation` — same shape (`id`, `name`, `selectedIds`, `chatMappings`, `transcript`)
- `fetchStateTopics` / `saveStateTopics` → `fetchConversations` / `saveConversations` — same endpoints, renamed for clarity
- New `ConversationSummary` type for sidebar list items:

```ts
type ConversationSummary = {
  id: string
  name: string
  memberCount: number
  updatedAt: string
  lastMessage: string | null
}
```

### Unchanged

- `chatTranscript.ts` — works with `topicId` which maps to `conversationId`
- `socket.ts` — same events, same protocol
- Server endpoints — `/api/state/topics` stays the same; client renames are cosmetic wrappers

### Replaced

- `markdownTranscript.ts` → `markdown-it` + plugins (`markdown-it-task-lists`) + `highlight.js` (oneDark theme)

## Visual Design

### Layout

- Flex row: `[ConversationSidebar (280px) | ChatArea (flex-grow)]`
- Sidebar collapsible to 0px via CSS transition (200ms ease)
- ChatArea: centered content column (max-width 768px for messages)
- Mobile (<768px): sidebar overlays as drawer with backdrop

### Color tokens (scoped to ChatView)

Reuses existing OKLCH custom properties from `App.vue`:

| Token | Value | Usage |
|-------|-------|-------|
| `--chat-user-bubble` | `oklch(64% 0.18 255 / 0.18)` | User message bubble background |
| `--chat-code-bg` | `oklch(12% 0.012 255)` | Code block background |
| `--chat-code-header` | `oklch(22% 0.014 255)` | Code block header bar |

### Messages

- **User:** right-aligned, accent-tinted bubble, no avatar
- **Bot:** left-aligned, no bubble background, square avatar (instance initial + accent color), bot name label above
- **Tool calls:** indented, border-left accent line, collapsible, ⚡ icon
- **Streaming:** pulsing `▍` cursor appended to last bot message while generating
- **Code blocks:** dark background, language label + copy + download buttons in header, `highlight.js` oneDark theme

### Composer

- Auto-growing textarea: 1 line → 18 lines max
- Left: ⊕ file attachment button
- Right: ↑ send button (accent when enabled, muted when disabled; replaced by ⏹ stop button during generation)
- Enter = send, Shift+Enter = newline
- File attachments shown as pills above textarea with × to remove

### Conversation Sidebar

- "New Chat" button at top with ✚ icon
- Search input below
- Date-grouped sections: Today / Yesterday / Previous 7 Days / Older
- Each item: stacked instance avatars left, conversation name, hover → ··· menu (rename, delete)
- Active item: accent background highlight

### Icons (Iconify `@iconify/vue`)

| Action | Icon |
|--------|------|
| New Chat | `mdi:plus` |
| Send | `mdi:send` |
| Attach file | `mdi:plus-circle-outline` |
| Copy | `mdi:content-copy` |
| Copied | `mdi:check` |
| Download code | `mdi:download` |
| Chat settings | `mdi:cog-outline` |
| Context menu | `mdi:dots-vertical` |
| Search | `mdi:magnify` |
| Collapse sidebar | `mdi:chevron-left` |
| Bot avatar fallback | `mdi:robot-outline` |
| Tool call | `mdi:lightning-bolt` |
| Stop generating | `mdi:stop-circle` |

## Interaction Flows

### New Chat

1. Click "New Chat" → `NewChatDialog` opens
2. Dialog: name input + instance picker (checkboxes, min 1 required) + Create/Cancel
3. On Create: save via `saveConversations`, switch to it, emit `ensure_topic_connections`
4. ChatArea shows empty state: "Send a message to start the conversation"

### Sending a Message

1. Type in composer (auto-grows), optionally attach files
2. Enter (without Shift) → emit `send_group_message`, append outbound to transcript
3. Composer resets, attachments cleared
4. While bot generating: streaming cursor `▍` pulses, Stop button replaces Send
5. Bot tokens arrive via `chat_event` → append to transcript in real-time
6. On completion: cursor removed, message finalized

### Copy Message

1. Hover bot message → Copy icon appears (top-right)
2. Click → clipboard write → icon changes to checkmark for 2s → reverts

### Sidebar Interactions

1. Click conversation → switch (load transcript, ensure connections)
2. Hover → ··· menu → Rename (inline edit) or Delete (confirmation)
3. Search → filters conversation list by name
4. Collapse toggle (chevron button or `S` hotkey) → sidebar slides to 0px

### File Attachments

1. Click ⊕ or paste image → file added to pending
2. Shown as pills above textarea with × to remove
3. On send: `media` array included in socket message

### Error States

- Connection failed for instance → avatar red ring, tooltip "Connection failed"
- No instances available → "No instances available" in NewChatDialog
- Empty message / no active members → Send button disabled

## Scope Exclusions

- No Edit message action
- No Regenerate action
- No debug events panel (raw logs removed)
- No Pin message
- No Delete single message
- No conversation folders
- No command picker (@, /, #)
- No math rendering (markdown-it-task-lists only, no KaTeX)

## Migration Notes

- `ChatPanel.vue` deleted, `ChatPanel.test.ts` rewritten for `ChatView.vue`
- `markdownTranscript.ts` deleted (replaced by markdown-it)
- `api.ts`: `StateTopic` aliased to `Conversation` for backward compat; `fetchConversations` wraps `fetchStateTopics`
- `App.vue` nav: "Chat Topics" label → "Chat"
- Server-side `/api/state/topics` endpoint unchanged — client renames are cosmetic

## Dependencies

- `@iconify/vue` — Iconify icon component for Vue 3
- `markdown-it` — Markdown parser
- `markdown-it-task-lists` — GFM task list support
- `highlight.js` — Syntax highlighting (oneDark theme included)
