# Branch-Specific Features – raffles/local (post-merge March 2026)

This document records features developed on `raffles/local`  
that survived the merge with `origin/main` on 13 March 2026.

Goal: help future merge conflict resolution (human or agent)  
understand intended behavior quickly.

## Feature Summary Table

| Feature                                     | Status | Primary files                                          | Key test / validation                  | Important config / default                    |
|---------------------------------------------|--------|--------------------------------------------------------|----------------------------------------|-----------------------------------------------|
| Telegram Topic support in groups            | ✅     | channels/telegram.py, cron/*, agent/tools/cron.py      | tests/test_cron_topic_delivery.py      | session_key includes `:topic:{thread_id}`     |
| Telegram groups → mention-only mode         | ✅     | channels/telegram.py                                   | manual + group_policy test             | `group_policy = "mention"` (default)          |
| Group commands via @mention                 | ✅     | channels/telegram.py → _on_message                     | manual                                 | `@BotName /command` → text message path       |
| Automatic fallback model on provider errors | ✅     | agent/loop.py, config/schema.py, cli/commands.py       | manual testing                         | `fallback_model: null` (default)              |
| "Thinking…" placeholder (PM only)           | ✅     | channels/telegram.py → _send_thinking_message          | tests/test_thinking_message.py         | skipped when `is_group == True`               |
| Typing indicator & ACK reaction             | ✅     | channels/telegram.py                                   | tests/test_typing_ack.py               | typing per chat+thread, reaction per msg      |
| Heartbeat results → DM / private only       | ✅     | heartbeat/service.py                                   | test_heartbeat_service.py + manual     | skips negative IDs and topic sub-sessions     |
| Media downloads → workspace/media/          | ✅     | channels/telegram.py                                   | tests/test_media_download.py           | falls back to `~/.nanobot/media`              |
| **TTS voice notes (Edge + OpenAI + Riva)**  | ✅     | providers/tts.py, tts/manager.py, channels/telegram.py | tests/test_tts.py (new)                | `tts.enabled = false` (default)               |
| **/trace command - AI thinking visibility** | ✅     | channels/telegram.py                                   | tests/test_trace_command_additional.py | `_trace_enabled[chat_id] = false` (default)   |
| **/stats command - token usage visibility** | ✅     | channels/telegram.py, utils/stats.py                   | tests/test_telegram_stats_command.py   | `/stats`, `/stats topic`, `/stats all`          |
| **Tool definitions caching (#2205)**        | ✅     | agent/tools/registry.py                                | tests/test_tool_registry_caching.py    | `_definitions_cache` invalidated on reg/unreg |
| **Incremental session saving (#2219)**      | ✅     | agent/loop.py, agent/subagent.py                       | tests/test_loop_incremental_save.py    | save offset tracks persisted content          |

## Detailed Descriptions & Merge Guidance

### 1. Telegram Topic support in groups + topic-aware cron

**Core behavior**
- Session key = `telegram:{chat_id}:topic:{message_thread_id}` (non-private + thread exists)
- `message_thread_id` carried in message metadata
- Cron jobs respect `threadId` field when delivering to group topics

**Files to protect during conflicts**
- nanobot/channels/telegram.py  
  → _derive_topic_session_key(), _build_message_metadata(), _on_message(), _forward_command()
- nanobot/cron/types.py, nanobot/cron/service.py
- nanobot/agent/tools/cron.py

**Resolution priority**
Prefer version that keeps `message_thread_id` in metadata and derives session key from it.

**Quick validation**
```bash
pytest tests/test_cron_topic_delivery.py -v
```

### 2. Mention-only mode for Telegram groups

**Core behavior**
- `group_policy = "mention"` → ignore unless @mentioned, text_mentioned or replied-to
- Clean helpers: _is_group_message_for_bot, _has_mention_entity, _ensure_bot_identity

**Files to protect during conflicts**
- channels/telegram.py → _is_group_message_for_bot, _has_mention_entity
- config/schema.py → TelegramConfig.group_policy

**Resolution priority**
Keep the helper-method version (more maintainable).  
Default should stay `"mention"`.

### 3. /model command – per-session model switch

**Core behavior**
- `/model` → show current
- `/model gpt-4o` → set for this session
- `/model reset` → revert to default (also accepts `/model default` as alias)
- Stored in `AgentLoop._model_overrides[session_key]`

**Files**
- agent/loop.py → _model_overrides, _handle_model_command, _run_agent_loop

**Resolution priority**
Keep `_model_overrides` dict + `effective_model = model_override or self.model`.
Reset keyword is `reset` (not `default`).

### 4. Automatic fallback model on provider errors

**Core behavior**
- Configure `fallback_model` in agent defaults to specify backup model when primary fails
- Automatically activates when primary model encounters 502/503 errors, timeouts, or other provider issues
- Transparent operation - users don't need to manually switch models
- Falls back to configured model only when specific provider errors detected

**Files**
- nanobot/config/schema.py → AgentDefaults.fallback_model field
- nanobot/agent/loop.py → _run_agent_loop with try/catch logic and fallback mechanism
- nanobot/cli/commands.py → Wiring of fallback_model parameter to AgentLoop

**Resolution priority**
Preserve the try/catch wrapper around provider.chat_with_retry that checks for provider errors and attempts fallback model.

**Quick validation**
Configure fallback_model in config and test with a temporarily unavailable primary provider.

### 4–8. Other smaller features (summary)

- Thinking draft message → PM only (`if is_group: return`)
- Typing + ACK reaction → per composite key (chat+thread)
- Heartbeat DM-only logic lives in `_pick_heartbeat_target()` inside `nanobot/cli/commands.py` (not `heartbeat/service.py`)
- Skips topic sub-sessions and negative Telegram chat IDs
- Media → `workspace/media/` when workspace configured

### 10. Tool definitions caching (#2205)

**Core behavior**
- Added caching to `ToolRegistry.get_definitions()` to prevent repeated traversal of tool sets and JSON schema construction during each iteration of the agent loop
- Introduces `_definitions_cache` field that starts as `None` and caches definitions on first `get_definitions()` call
- Automatically invalidates cache when tools are registered/unregistered via `register()`/`unregister()` methods
- Maintains backward compatibility with automatic cache invalidation

**Files to protect during conflicts**
- nanobot/agent/tools/registry.py → ToolRegistry class with caching implementation
- tests/test_tool_registry_caching.py → Comprehensive tests for caching functionality

**Resolution priority**
Preserve the caching mechanism that improves performance by avoiding redundant schema generation during agent loop iterations.

**Quick validation**
```bash
pytest tests/test_tool_registry_caching.py -v
```

### 11. Incremental session saving (#2219)

**Core behavior**
- Implements incremental session saving for agent loops to prevent data loss when operations crash or get cancelled mid-process
- Adds an incremental save mechanism that persists messages after each tool call completes, rather than waiting until the entire loop finishes
- Uses a callback approach with a save offset to track already-persisted content, ensuring only new messages get written
- Zero destructive changes to existing logic with minimal I/O overhead and preserved compatibility

**Files to protect during conflicts**
- nanobot/agent/loop.py → AgentLoop class with incremental save implementation
- nanobot/agent/subagent.py → SubAgent class adjustments for incremental saving
- tests/test_loop_incremental_save.py → Tests for incremental save functionality

**Resolution priority**
Keep the incremental save functionality that protects against data loss during multi-step agent operations.

**Quick validation**
```bash
pytest tests/test_loop_incremental_save.py -v
```