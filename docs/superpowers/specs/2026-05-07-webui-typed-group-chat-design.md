# WebUI Typed Group Chat Design

## Goal

Make Chat Topics behave like real multi-bot rooms. Topic membership should imply connection: when a bot is added to a topic, the webui connects or attaches it automatically. Opening an existing topic should render saved history immediately and auto-connect every enabled bot already in the topic.

The chat content page should use the approved modern two-column layout with a member bar, not the previous boxy picker-plus-transcript layout.

## Scope

In scope:

- Preserve existing `/data/webui-state.json` topics and transcript history.
- Extend topics with per-instance chat mappings.
- Replace manual `Connect selected` workflow with automatic membership-driven connection.
- Send typed nanobot WebSocket envelopes using `chat_id`.
- Add file attachment UI and typed-envelope media forwarding for the chat composer.
- Add copy response as markdown for assistant/tool/reasoning transcript entries.
- Keep the dashboard token, nanobot admin tokens, WebSocket tokens, and upstream URLs server-side only.

Out of scope for this slice:

- Full room-agent personas or orchestration policies.
- Cross-topic summarization or context compression.
- Container lifecycle controls.
- Server-side file browser for historical media.

## Layout

Use the selected `B. Two Column With Member Bar` structure:

- Left column: topic list, search/create affordance, compact saved-topic metadata.
- Main column header: topic title, saved message count/status, optional actions such as retry failed connections.
- Member bar below header: topic bot chips with status (`attached`, `attaching`, `failed`, `disabled`) and an `Add bot` affordance.
- Center transcript: modern LLM-chat style, not boxed cards for every message.
- Composer: floating rounded composer pinned to the bottom of the chat content region.
- Attachment controls: plus/file button, pending attachment tray, and attached file chips on sent messages.

The transcript visual style should be closer to modern DeepSeek/OpenAI/Gemini/Anthropic chat surfaces:

- Fewer enclosing panels inside the transcript.
- Softer vertical rhythm and whitespace.
- User messages may use subtle bubbles.
- Assistant messages should be mostly text-first, with lightweight speaker labels/avatar chips.
- Tool/reasoning blocks remain visually distinct but should not feel like heavy bordered cards.
- Mobile stacks topics above the chat workspace and keeps the composer reachable.

## Topic State

Persist topic state as an extension of the existing shape:

```ts
type Topic = {
  id: string
  name: string
  selectedIds: string[]
  chatMappings?: Record<string, {
    chatId: string
    status: 'pending' | 'attached' | 'error'
    lastError?: string
  }>
  transcript: TranscriptState
}
```

`selectedIds` remains the storage field for compatibility, but the UI labels it as bots or members in the topic. Legacy topics without `chatMappings` are normalized to `{}` in memory and persisted on the next topic mutation. Legacy transcript history is never dropped.

Removing a bot from a topic removes it from future sends and auto-connect attempts. Existing transcript entries from that bot remain visible as history.

## Connection Behavior

Opening or switching to a topic:

1. Render saved transcript history immediately.
2. Read topic member instance IDs from `selectedIds`.
3. Ignore disabled instances for connection attempts, but show them as disabled if they remain in persisted membership.
4. For each enabled member, ensure an upstream connection exists.
5. If a `chatMappings[instanceId].chatId` exists, send `{ type: 'attach', chat_id }`.
6. If no mapping exists, send `{ type: 'new_chat' }`.
7. When upstream emits `attached`, store the returned `chatId` in `chatMappings[instanceId]` and persist topics.

Adding a bot to a topic:

1. Add the instance ID to the topic membership.
2. Persist membership.
3. Start the same ensure/attach/new-chat flow for that one instance.

Sending a message:

1. Append the local user message to the transcript.
2. For each enabled member with an attached mapping, send a typed envelope:

```json
{ "type": "message", "chat_id": "...", "content": "...", "media": [] }
```

3. If an enabled member has no attached mapping, surface a per-instance status/error instead of silently dropping the message.
4. Persist transcript updates.

The old `Connect selected` button is removed. A retry action can appear only for failed topic members.

## Attachments

The composer supports selecting files for the current outbound message.

Initial implementation should support the media shape already accepted by nanobot WebSocket envelopes:

```ts
type ComposerMedia = {
  data_url: string
  name?: string
}
```

The UI shows pending attachment chips before send and attachment chips on the local user transcript entry after send. The server-side nanobot channel still enforces MIME/count/size limits. If upstream rejects media, the normalized error event is shown in the topic transcript/debug events.

This slice does not need a permanent local binary store in the webui. Attachments are read in the browser and sent through the BFF to nanobot in typed envelopes.

## Markdown Copy

Each non-user transcript entry has a lightweight `Copy Markdown` action. The copied text should be the original markdown/source text for that response, not rendered HTML. For tool and reasoning entries, copy the text body with a small markdown heading prefix, for example:

```md
### Alpha Reasoning

checking output...
```

For assistant message entries, copy the entry text exactly. The UI should report copied/failure state without disrupting the transcript.

## Chat Bridge

The Socket.IO BFF remains the browser-facing transport. It should support topic-aware events while preserving existing authorization and redaction boundaries.

Browser-to-BFF events:

- `ensure_topic_connections`: `{ topicId, members, chatMappings }`
- `add_topic_member`: optional convenience event if kept server-driven; otherwise the browser can update state and call `ensure_topic_connections`.
- `send_group_message`: `{ topicId, text, media?, chatMappings, memberIds }`

BFF-to-browser events:

- Existing `chat_event` shape, including `instanceId`, normalized `event`, and `chatId`.
- `attached` events are used by the browser to update topic mappings.
- Connection lifecycle events remain per instance.

The bridge sends typed upstream frames to nanobot:

- `{ type: 'new_chat' }`
- `{ type: 'attach', chat_id }`
- `{ type: 'message', chat_id, content, media? }`

The bridge must not let the browser provide arbitrary upstream URLs or tokens. It only accepts configured instance IDs.

Because nanobot upstream `attached` events include `chat_id` but not the webui `topicId`, the BFF must correlate attach/new-chat requests before relaying them to the browser:

- For `attach`, the BFF already knows `{ topicId, instanceId, chatId }` from `ensure_topic_connections`; relayed `attached` events include that `topicId` when the returned `chat_id` matches.
- For `new_chat`, the BFF records the pending `{ topicId, instanceId }` request until the next `attached` event from that upstream, then relays `chat_event` with `topicId`, `instanceId`, and `chatId`.
- If multiple topics request `new_chat` for the same instance concurrently, the BFF serializes those requests per instance so the next `attached` response is unambiguous.
- Existing normal upstream events are routed by `topicId` using the persisted/reported `chatMappings` table.

## Error Handling

- Unknown instance: visible per-instance error.
- Disabled instance: shown as disabled; no auto-connect attempt.
- Invalid or missing topic/member payload: emit a safe error event.
- Missing chat mapping during send: show `not attached` for that member and continue attached members.
- Upstream connection failure: mark member failed and expose retry.
- `attached` event for a non-active topic should update that topic mapping without stealing the visible transcript.
- Events are routed by `topicId + instanceId + chatId` so one topic cannot receive another topic's replies.

## Tests

Frontend/component tests:

- Opening a persisted topic renders its history and auto-connects its saved enabled members.
- Adding a bot to a topic persists membership and auto-connects that bot.
- The manual `Connect selected` workflow is gone.
- Sending after attachment uses topic members, not a separate selected checkbox list.
- Switching topics auto-connects each topic's own members and does not leak events across topics.
- Disabled saved members are displayed but not auto-connected.
- Composer supports pending file attachments and passes media on send.
- `Copy Markdown` copies assistant response source markdown.

Server/bridge tests:

- `ensure_topic_connections` sends `new_chat` when no mapping exists.
- `ensure_topic_connections` sends `attach` when a mapping exists.
- `send_group_message` sends typed `message` envelopes with each mapped `chat_id`.
- Invalid payloads emit safe errors.
- Existing dashboard socket authorization is preserved.

Type/persistence tests:

- Legacy topics without `chatMappings` normalize without dropping transcript history.
- Saved mappings survive reload.
