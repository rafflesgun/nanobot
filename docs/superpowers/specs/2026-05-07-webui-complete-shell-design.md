# WebUI Complete Shell Design

## Goal

Build the approved B-style dashboard: a dark primary sidebar with `Overview`, `Chat Topics`, `Instances`, and `Manage`, plus a Manage subnav scoped to a selected target instance. Fix the remaining bright card styling and render chat output as readable assistant/user transcript blocks instead of raw protocol events.

## Scope

This implementation establishes the complete product shell and the first usable behavior for each area. Existing backend APIs stay in place for status, settings, and logs. New dashboard-owned state is local to the webui process for this slice, with `/data` reserved for persistent storage in the next slice. Management sections without nanobot admin APIs render clear unsupported states rather than fake controls.

## Navigation

- Primary sidebar: `Overview`, `Chat Topics`, `Instances`, `Manage`.
- Top bar: compact instance status strip and logout.
- Manage page: target instance selector plus subnav for `Settings`, `Subagents`, `Logs`, `Usage`, `Costing`, `Session`, `Memory`, `Restart`.
- `Settings` and `Logs` reuse the existing working panels.
- `Subagents`, `Usage`, `Costing`, `Session`, `Memory`, and `Restart` render dark placeholder panels that describe the missing backend capability and avoid pretending actions succeeded.

## Dark Theme

All cards, forms, transcripts, selects, log tails, status cards, and placeholder panels must use dark surfaces. Bright white/light-gray panel backgrounds are not allowed in authenticated dashboard components except deliberate alert states.

## Chat Transcript

Chat event handling separates operator-readable transcript from debug protocol events.

- `delta` events append to one assistant message per `instanceId` and `chatId`.
- `stream_end`, `turn_end`, and lifecycle events do not create transcript messages.
- Error/detail events create visible system messages.
- User sends create outbound transcript messages.
- Raw protocol events remain available in a collapsible debug drawer.

## Chat Topics

`Chat Topics` introduces a local topic/channel sidebar with create/select/delete behavior in the client. Each topic stores selected instance ids and its own transcript for the session. Persistent `/data` storage follows in the next implementation slice.

## Instances

`Instances` provides dashboard-owned CRUD shell behavior over the public instance list: create/edit/disable/delete forms in the browser state, with clear labels that persisted server-side storage is pending. Secrets are accepted only in form fields and are never shown after save.

## Testing

- Add regression tests for dark surface tokens in Vue components.
- Add unit tests for chat event aggregation and ignored terminal events.
- Add component tests for chat debug drawer, topics, instance CRUD shell, and Manage subnav.
- Run full webui tests, build, TypeScript checks, compose config, and Docker smoke before completion.
