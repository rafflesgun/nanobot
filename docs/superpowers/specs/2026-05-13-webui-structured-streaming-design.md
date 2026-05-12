# WebUI Structured Streaming Design

## Goal

Improve WebUI chat streaming so reasoning/thinking, tool calls, sub-agent activity, and final assistant text stream as separate, understandable transcript blocks from the first token through `turn_end`.

The design is hybrid:

- Support structured backend events where nanobot can emit them.
- Keep old `delta`, `message`, `stream_end`, and `turn_end` compatibility.
- Parse inline `<think>...</think>` from legacy assistant text as a fallback.

## Event Model

Existing websocket events remain valid:

- `delta`
- `message`
- `stream_end`
- `turn_end`
- `attached`
- `error`

New typed events should be added incrementally:

- `reasoning.delta`
- `message.delta`
- `tool_call.start`
- `tool_call.delta`
- `tool_call.end`
- `subagent.start`
- `subagent.delta`
- `subagent.end`

Each typed event should carry:

- `chat_id`
- `stream_id`
- `turn_id` when available; otherwise clients derive a turn boundary from `stream_id`
- `kind`: `message`, `reasoning`, `tool`, `subagent`, or `progress`
- Optional metadata: `name`, `status`, `detail`, `tool_call_id`, `subagent_name`

The WebUI should prefer typed events when present. Legacy `delta` continues to mean normal assistant text unless inline `<think>` parsing splits it into reasoning and final-message segments.

## Backend Flow

The nanobot agent loop should classify stream output where possible before it reaches the websocket channel:

- Provider reasoning/thinking metadata becomes `reasoning.delta`.
- Normal assistant content becomes `message.delta`.
- Tool lifecycle events become `tool_call.start`, `tool_call.delta`, and `tool_call.end`.
- Sub-agent lifecycle events become `subagent.start`, `subagent.delta`, and `subagent.end`.
- Unclassified provider chunks remain legacy `delta` so no output is lost.

The websocket channel should pass through typed event metadata while preserving current legacy behavior for existing clients.

## WebUI Flow

`chatTranscript.ts` should remain the single normalization point that converts wire events into transcript entries. UI components should only render normalized entries.

Each assistant turn can contain multiple transcript entries:

- One visible reasoning stream.
- Zero or more tool-call streams.
- Zero or more sub-agent streams.
- One final assistant message stream.

Stream matching should prefer `stream_id + kind`. If `stream_id` is missing, it falls back to `instanceId + chatId + kind`.

Legacy inline `<think>...</think>` parsing runs on `delta` and `message` content:

- Text inside `<think>` becomes `kind: "reasoning"`.
- Text outside `<think>` becomes `kind: "message"`.
- Partial tags must work across chunk boundaries.
- An unfinished `<think>` block remains a reasoning block while streaming and at `turn_end`.

## UI Behavior

Reasoning/thinking text should be visible by default. It should still look visually secondary:

- Dimmer color than final assistant text.
- Dedicated "Thinking" label.
- Collapsible toggle, expanded by default for new output.
- Raw text preserved exactly, including newlines.

Tool calls and sub-agent calls should render as timeline-style collapsible blocks:

- Start event creates a running block.
- Delta events append detail/output text.
- End event marks completion and records status.
- If no end event arrives, `turn_end` marks the block ended.

The final assistant response remains a normal assistant bubble separate from reasoning/tool/sub-agent blocks.

## Error Handling

- Missing `stream_id`: fall back to `instanceId + chatId + kind`.
- Malformed or unclosed `<think>` tags: keep the captured text as reasoning.
- Tool/sub-agent start without end: leave running until `turn_end`, then mark ended.
- Unknown event kind: store in debug events and render as a muted system/progress line if it has user-visible text.
- Structured backend failure: legacy `delta`/`message` still displays output.

## Compatibility

- Existing websocket clients keep receiving compatible events.
- WebUI accepts both legacy and typed events during rollout.
- Backend can add typed events incrementally: reasoning first, then tool lifecycle, then sub-agent lifecycle.
- `nanobot-webui/src/server/chatBridge.ts` should mostly pass through new fields; only types/tests need updates unless filtering blocks them.

## Testing

Add tests for:

- Incremental `<think>` parsing across chunk boundaries.
- Separate reasoning and final answer entries from legacy `delta` streams.
- Second-turn separation using `stream_id` when present.
- Fallback separation with `instanceId + chatId + kind` when `stream_id` is missing.
- Tool-call start/delta/end transcript lifecycle.
- Sub-agent start/delta/end transcript lifecycle.
- Backward-compatible legacy `delta` and `message` behavior.
- UI rendering for expanded-by-default reasoning and separate final answer.

## Non-Goals

- Do not expose nanobot admin tokens, websocket tokens, upstream URLs, or filesystem paths to the browser.
- Do not remove legacy `delta`, `message`, `stream_end`, or `turn_end` support.
- Do not require every provider to emit structured reasoning immediately.
