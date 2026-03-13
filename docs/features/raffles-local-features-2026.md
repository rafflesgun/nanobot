# Branch-Specific Features – raffles/local (post-merge March 2026)

This document records features developed on `raffles/local`  
that survived the merge with `origin/main` on 13 March 2026.

Goal: help future merge conflict resolution (human or agent)  
understand intended behavior quickly.

## Feature Summary Table

| Feature                                      | Status | Primary files                                      | Key test / validation                        | Important config / default                  |
|----------------------------------------------|--------|----------------------------------------------------|----------------------------------------------|---------------------------------------------|
| Telegram Topic support in groups             | ✅     | channels/telegram.py, cron/*, agent/tools/cron.py | tests/test_cron_topic_delivery.py            | session_key includes `:topic:{thread_id}`   |
| Telegram groups → mention-only mode          | ✅     | channels/telegram.py                               | manual + group_policy test                   | `group_policy = "mention"` (default)        |
| Group commands via @mention                  | ✅     | channels/telegram.py → _on_message                 | manual                                       | `@BotName /command` → text message path     |
| /model command – per-session model override  | ✅     | agent/loop.py                                      | tests/test_model_switch.py                   | stored in `_model_overrides[session_key]`   |
| "Thinking…" placeholder (PM only)            | ✅     | channels/telegram.py → _send_thinking_message      | tests/test_thinking_message.py               | skipped when `is_group == True`             |
| Typing indicator & ACK reaction              | ✅     | channels/telegram.py                               | tests/test_typing_ack.py                     | typing per chat+thread, reaction per msg    |
| Heartbeat results → DM / private only        | ✅     | heartbeat/service.py                               | test_heartbeat_service.py + manual           | skips negative IDs and topic sub-sessions   |
| Media downloads → workspace/media/           | ✅     | channels/telegram.py                               | tests/test_media_download.py                 | falls back to `~/.nanobot/media`            |

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

**Files**
- channels/telegram.py → _is_group_message_for_bot, _has_mention_entity
- config/schema.py → TelegramConfig.group_policy

**Resolution priority**
Keep the helper-method version (more maintainable).  
Default should stay `"mention"`.

### 3. /model command – per-session model switch

**Core behavior**
- `/model` → show current
- `/model gpt-4o` → set for this session
- `/model default` → revert
- Stored in `AgentLoop._model_overrides[session_key]`

**Files**
- agent/loop.py → _model_overrides, _handle_model_command, _run_agent_loop

**Resolution priority**
Keep `_model_overrides` dict + `effective_model = model_override or self.model`

### 4–8. Other smaller features (summary)

- Thinking draft message → PM only (`if is_group: return`)
- Typing + ACK reaction → per composite key (chat+thread)
- Heartbeat → DM only (skip negative IDs & topic sessions)
- Media → `workspace/media/` when workspace configured

## Smoke / Validation Commands (after merge/conflict fix)

```bash
# Basic model switch
nanobot agent --message "/model gpt-4o-mini"

# Cron topic delivery (if cron service running)
pytest tests/test_cron_topic_delivery.py -v

# Manual group+topic test (in Telegram)
# 1. In group topic → @BotName hello
# 2. In same topic → @BotName /model claude-3.5-sonnet
# 3. Reply to bot message → should continue in same topic
```

Last updated: 13 March 2026 – after merge with main