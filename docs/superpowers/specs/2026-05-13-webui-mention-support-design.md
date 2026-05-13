# @ Mention Support in Chat UI

**Date**: 2026-05-13
**Status**: Approved

## Summary

Add `@AgentName` mention support to the chat composer. Typing `@` triggers an autocomplete dropdown of conversation members. On send, if any `@mention` is found, the message routes only to the mentioned agent(s); otherwise it goes to all members (current default behavior).

## Routing Semantics

- `@Alpha` in a message → only Alpha receives and responds
- `@Alpha @Beta` → both Alpha and Beta respond
- No `@mention` → all conversation members respond (current behavior, unchanged)
- Mention of a non-member → ignored in routing; rendered as highlighted text
- `@all` / `@everyone` → not supported; renders as plain highlighted text, no special routing

## Composer: Autocomplete Dropdown

### Trigger

Typing `@` in the textarea opens the dropdown. The `@` must be at the start of the line, after whitespace, or at position 0 to trigger. Mid-word `@` (e.g., `email@domain`) does not trigger.

### Filter

Characters typed after `@` filter the dropdown list using case-insensitive substring match on the agent name. The filter updates on every keystroke while the dropdown is open.

### Dropdown UI

- Positioned above the textarea, anchored to the textarea width
- Max 6 items visible with scroll for overflow
- Each item shows: avatar (first letter + color, same style as MessageBubble bot-avatar), agent name, connection status dot (green/yellow/red matching existing status colors)
- No results state: show "No matching agents" dimmed text

### Selection

- **Click** or **Enter** or **Tab**: inserts `@AgentName ` (trailing space) at the cursor, closes dropdown
- **Escape**: closes dropdown without inserting
- **Clicking outside**: closes dropdown without inserting
- **Backspace on empty filter** (i.e., just `@`): closes dropdown

### Keyboard Navigation

While dropdown is open, arrow keys cycle through items. The selected item has a highlight background. Enter/Tab confirms the highlighted item.

## Mention Parsing & Routing

`parseMentions(text: string, members: PublicInstance[]): { mentionedIds: string[], text: string }`

- Scans text for `@Name` tokens
- Matches tokens against conversation member names (case-insensitive exact match)
- Returns the list of matched member IDs and the original text unchanged
- Multiple mentions are supported
- If a name has spaces, it cannot be matched via `@` (graceful degradation — no route change)

### Send Flow Change

In `ChatView.vue`, before emitting `send_group_message`:

```
const { mentionedIds } = parseMentions(text, activeMembers)
const memberIds = mentionedIds.length > 0 ? mentionedIds : allMemberIds
socket.emit('send_group_message', { topicId, text, memberIds, chatMappings })
```

The `text` sent to agents includes the `@Name` tokens — agents may choose to interpret them or ignore them.

## Visual Rendering in Message Bubbles

In `MessageBubble.vue`, `@AgentName` patterns in both user and bot messages are rendered with a highlighted style:

- Subtle background pill (accent color at low opacity)
- Accent-colored text for the `@Name`
- Achieved via a post-render regex replace on the HTML output from markdown-it

Regex pattern: `/@(\w+)/g` applied to the rendered HTML, wrapping matches in a `<span class="mention">` element. Only matches that correspond to a known instance name get the highlight; others remain plain text.

## Edge Cases

| Case | Behavior |
|------|----------|
| Partial name typed, not selected from dropdown, sent as-is | `@Al` does not match `Alpha`; falls through to all-members routing |
| Mention of non-member agent | Highlighted in bubble but ignored in routing |
| Multiple mentions | Routes to union of all mentioned agents |
| `@` at end of message with no name | Dropdown opens; if sent without selection, `@` is plain text, all-members routing |
| Bot message contains `@AgentName` | Rendered with same highlight style |
| Name with spaces | Cannot be `@`-mentioned (graceful — no match) |

## Components Changed

| Component | Change |
|-----------|--------|
| `ChatComposer.vue` | Add dropdown, `@` detection, keyboard nav, accept `members` prop |
| `ChatArea.vue` | Pass `members` to ChatComposer |
| `ChatView.vue` | Add `parseMentions()` call before `send_group_message` |
| `MessageBubble.vue` | Highlight `@Name` patterns in rendered markdown |
| `chatTranscript.ts` | Add `parseMentions()` utility function |

## Out of Scope

- `@all` / `@everyone` broadcast mentions
- Rich mention chips (contenteditable approach)
- Mention notifications / push alerts
- Mentioning users (only agents/instances)
