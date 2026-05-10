# Nanobot Dashboard Design System

## Color Palette (OKLCH)

All colors use OKLCH color space. CSS custom properties defined in `App.vue` `:root`.

| Token        | Value                    | Usage                          |
|--------------|--------------------------|--------------------------------|
| `--bg`       | `oklch(15% 0.012 255)`  | Page background                |
| `--surface`  | `oklch(19% 0.014 255)`  | Card / panel background        |
| `--surface-2`| `oklch(23% 0.014 255)`  | Elevated surface (hover, etc.) |
| `--fg`       | `oklch(94% 0.006 255)`  | Primary text                   |
| `--muted`    | `oklch(66% 0.012 255)`  | Secondary / disabled text      |
| `--border`   | `oklch(29% 0.012 255)`  | Borders, dividers              |
| `--accent`   | `oklch(64% 0.18 255)`   | Primary accent (blue-violet)   |
| `--success`  | `oklch(70% 0.14 145)`   | Online / connected status      |
| `--warn`     | `oklch(78% 0.14 85)`    | Warning state                  |
| `--danger`   | `oklch(68% 0.17 25)`    | Error / offline status         |

## Typography

| Token           | Value                                                            |
|-----------------|------------------------------------------------------------------|
| `--font-display`| `-apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui` |
| `--font-body`   | `-apple-system, BlinkMacSystemFont, 'SF Pro Text', system-ui`    |
| `--font-mono`   | `ui-monospace, 'SF Mono', Menlo, Monaco, Consolas, monospace`   |

## Scrollbar

Dark-themed thin scrollbar:
- Width: 6px
- Track: transparent
- Thumb: `oklch(30% 0.012 255)`, hover `oklch(40% 0.014 255)`
- Firefox: `scrollbar-width: thin; scrollbar-color: oklch(30% 0.012 255) transparent`

## Layout

### Shell
- App grid: `268px sidebar | 1fr main` (collapsed: `64px | 1fr`)
- Topbar: sticky, `min-height: 62px`, backdrop blur
- Refresh button: only shown on Overview tab
- No "New Chat" button in topbar (chat has its own sidebar)
- Content: `max-width: 1440px`, `padding: 22px`
- Chat content: `padding: 0`, `max-width: none` (fills available space)

### Sidebar
- Brand: logo icon (`mdi:robot-outline`) + "nanobot" title + "agents dashboard" subtitle
- Collapse button: `mdi:chevron-left` / `mdi:chevron-right` (not ⌘)
- No "Workspace" section label (removed — added no value)
- No count badges on nav items (removed — added noise)
- Collapsed state: logo icon stays 30×30px, only icons visible for nav items

### Navigation Items
| Tab key   | Label          | Icon                        |
|-----------|----------------|-----------------------------|
| overview  | Overview       | `mdi:view-dashboard-outline`|
| chat      | Chat           | `mdi:chat-outline`          |
| agents    | Agents         | `mdi:robot-outline`         |
| manage    | Manage Agents  | `mdi:cog-outline`           |
| logs      | Logs           | `mdi:file-document-outline` |

- "Agents" replaces "Instances" — nanobot instances are called agents
- "Manage Agents" replaces "Manage" — clarifies purpose (config/settings per agent)
- Icons are critical: they serve as the sole identifier when sidebar is collapsed

### Chat Layout
- ChatView: `height: calc(100vh - 62px)`, flex row
- ConversationSidebar: `width: 280px`, collapsible
- ChatArea: flex column, full height
  - ChatHeader: flex-shrink 0, contains sidebar toggle + title + member avatars + add-member
  - MessageList: `flex: 1; overflow-y: auto` (only scrollable area)
  - ChatComposer: `flex-shrink: 0`, pinned to bottom

## Chat UI

### Composer (ChatGPT-style)
- Single-line input by default, auto-grows with content
- Pill-shaped container (`border-radius: 24px`)
- Single line: `[+] [text...] [send]` in one row
- Multi-line: text above, `[+]` and `[send]` stay at bottom right
- Enter to send, Shift+Enter for newline
- Send button: circular, accent color, `mdi:arrow-up` icon
- Attach button: circular, `mdi:plus-circle-outline`
- Stop button: `mdi:stop-circle`, danger color, pulse animation

### Messages
- User messages: right-aligned bubble, `oklch(64% 0.18 255 / 0.18)` background, rounded corners
- Bot messages: left-aligned, avatar + name + content, markdown rendered
- Tool/reasoning: collapsible block, indented
- Copy action: below message content, icon button with border, visible on hover
  - Icon: `mdi:content-copy` / `mdi:check`, size 14px
  - Style: `border: 1px solid var(--border); border-radius: 6px; background: var(--surface)`
  - Clipboard fallback: `document.execCommand('copy')` when `navigator.clipboard` unavailable

### Chat Header
- Left: sidebar toggle button → chat title → member avatars → add-member button
- No settings button (removed to avoid dead UI)
- Sidebar toggle: `mdi:chevron-left` / `mdi:chevron-right`

### Member Avatars
- Circle, 28px, border color reflects connection status (green=connected, red=error, gray=other)
- Remove button (×) appears on hover
- Add-member opens `AddMemberDialog` (NOT NewChatDialog)

### Conversations Sidebar
- Date groups: Today / Yesterday / Previous 7 Days / Older
- Search bar, new chat button
- Collapsible to 0px (not icon strip)

### Sending Messages
- `canSend` requires ALL members to have `chatMappings[memberId].status === 'attached'`
- Ensures `send_group_message` is only emitted after upstream WebSocket connections are established
- Prevents "not attached" errors from server

## Components

| Component          | Purpose                                      |
|--------------------|----------------------------------------------|
| ChatView           | Main orchestrator: socket, state, dialogs    |
| ChatArea           | Layout: header + messages + composer         |
| ChatHeader         | Title, members, sidebar toggle               |
| MessageList        | Scrollable message container                 |
| MessageBubble      | Individual message (user/bot/tool/reasoning) |
| CodeBlock          | Syntax-highlighted code with copy/download   |
| ToolCallBlock      | Collapsible tool call display                |
| ChatComposer       | Input with auto-grow, attach, send/stop      |
| ConversationSidebar| Conversation list with search, date groups   |
| ConversationItem   | Single conversation row                      |
| NewChatDialog      | Create new conversation (name + instance pick)|
| AddMemberDialog    | Add instance to existing conversation        |

## Icons

All icons use `@iconify/vue` (`Icon` component). Tree-shakable, 3000+ icon sets.
Common icons:
- `mdi:robot-outline` (logo, Agents nav)
- `mdi:view-dashboard-outline` (Overview nav)
- `mdi:chat-outline` (Chat nav)
- `mdi:cog-outline` (Manage Agents nav)
- `mdi:file-document-outline` (Logs nav)
- `mdi:plus`, `mdi:plus-circle-outline`, `mdi:close`, `mdi:chevron-left`, `mdi:chevron-right`
- `mdi:content-copy`, `mdi:check`, `mdi:download`, `mdi:arrow-up`, `mdi:stop-circle`
- `mdi:magnify`, `mdi:message-text-outline`

## Markdown Rendering

`markdown-it` + `highlight.js` + `markdown-it-task-lists` via `chat/markdown.ts`.
Code blocks extracted from rendered HTML and replaced with `CodeBlock.vue` component.
