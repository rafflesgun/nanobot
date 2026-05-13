# @ Mention Support in Chat UI

**Date**: 2026-05-13
**Status**: Approved

## Summary

Add `@AgentName` and `@all` mention support to the chat composer. Typing `@` triggers an autocomplete dropdown of conversation members plus an `@all` option. Routing depends on group size and mentions.

## Routing Semantics

### Single-agent conversations (1 member)

No `@mention` needed. Messages are sent to the sole agent automatically (current behavior, unchanged). `@mentions` are allowed but have no routing effect.

### Multi-agent conversations (2+ members)

Mentions are **required** for routing:

| Input | Routing |
|-------|---------|
| No `@mention` | **Nobody receives the message** — send is blocked with a hint |
| `@all` | All conversation members receive the message |
| `@Alpha` | Only Alpha receives the message |
| `@Alpha @Beta` | Both Alpha and Beta receive the message |
| `@Alpha @all` | `@all` wins — all members receive (explicit broadcast) |

### General rules

- Mention of a non-member → ignored in routing; rendered as highlighted text
- `@all` is a reserved keyword — always appears as the first item in the autocomplete dropdown

## Composer: Autocomplete Dropdown

### Trigger

Typing `@` in the textarea opens the dropdown. The `@` must be at the start of the line, after whitespace, or at position 0 to trigger. Mid-word `@` (e.g., `email@domain`) does not trigger.

### Filter

Characters typed after `@` filter the dropdown list using case-insensitive substring match on the agent name. The filter updates on every keystroke while the dropdown is open. `@all` always appears as the first item (unless the filter excludes "all").

### Dropdown UI

- Positioned above the textarea, anchored to the textarea width
- Max 6 items visible with scroll for overflow
- **First item** (when in multi-agent conversation): `@all` with a group/broadcast icon and label "all members"
- Subsequent items show: avatar (first letter + color, same style as MessageBubble bot-avatar), agent name, connection status dot (green/yellow/red matching existing status colors)
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
- `@all` (case-insensitive) is a reserved keyword → resolves to all member IDs
- Other tokens match against conversation member names (case-insensitive exact match)
- Returns the list of matched member IDs and the original text unchanged
- If `@all` is present, `mentionedIds` contains all member IDs (broadcast wins over individual mentions)
- Multiple individual mentions are supported
- If a name has spaces, it cannot be matched via `@` (graceful degradation — no route change)

### Send Flow Change

In `ChatView.vue`, before emitting `send_group_message`:

```
const { mentionedIds } = parseMentions(text, activeMembers)
if (activeMembers.length >= 2 && mentionedIds.length === 0) {
  // Multi-agent conversation with no mentions — block send
  // Show hint: "Mention @all or @AgentName to route your message"
  return
}
const memberIds = mentionedIds.length > 0 ? mentionedIds : allMemberIds
socket.emit('send_group_message', { topicId, text, memberIds, chatMappings })
```

The `text` sent to agents includes the `@Name` tokens — agents may choose to interpret them or ignore them.

## Visual Rendering in Message Bubbles

In `MessageBubble.vue`, `@AgentName` patterns in both user and bot messages are rendered with a highlighted style:

- Subtle background pill (accent color at low opacity)
- Accent-colored text for the `@Name`
- Achieved via a post-render regex replace on the HTML output from markdown-it

Regex pattern: `/@(\w+)/g` applied to the rendered HTML, wrapping matches in a `<span class="mention">` element. `@all` and matches that correspond to a known instance name get the highlight; other `@words` remain plain text.

## Composer Hint for Multi-Agent

When the conversation has 2+ members and the message text contains no `@mention`, the composer shows a dimmed hint below the textarea: "Mention @all or @AgentName to send". This disappears once a mention is present.

## Edge Cases

| Case | Behavior |
|------|----------|
| Partial name typed, not selected from dropdown, sent as-is | `@Al` does not match `Alpha`; in multi-agent convos this counts as "no mention" → send blocked |
| Mention of non-member agent | Highlighted in bubble but ignored in routing |
| Multiple mentions | Routes to union of all mentioned agents |
| `@all` + individual mentions | `@all` wins — broadcasts to all members |
| `@` at end of message with no name | Dropdown opens; if sent without selection in multi-agent, send blocked |
| Bot message contains `@AgentName` | Rendered with same highlight style |
| Name with spaces | Cannot be `@`-mentioned (graceful — no match) |
| Single-agent conversation | No mention required; `@mentions` allowed but have no routing effect |

## Components Changed

| Component | Change |
|-----------|--------|
| `ChatComposer.vue` | Add dropdown, `@` detection, keyboard nav, accept `members` prop |
| `ChatArea.vue` | Pass `members` to ChatComposer |
| `ChatView.vue` | Add `parseMentions()` call before `send_group_message` |
| `MessageBubble.vue` | Highlight `@Name` patterns in rendered markdown |
| `chatTranscript.ts` | Add `parseMentions()` utility function |

## Out of Scope

- Rich mention chips (contenteditable approach)
- Mention notifications / push alerts
- Mentioning users (only agents/instances)
- `@everyone` (use `@all` instead)
