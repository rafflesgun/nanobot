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
| Automatic fallback model on provider errors | ✅     | agent/loop.py, config/schema.py, cli/commands.py, agent/subagent.py | manual testing with quota exhaustion | `fallback_model: null` (default)              |
| "Thinking…" placeholder (PM only)           | ✅     | channels/telegram.py → _send_thinking_message          | tests/test_thinking_message.py         | skipped when `is_group == True`               |
| Typing indicator & ACK reaction             | ✅     | channels/telegram.py                                   | tests/test_typing_ack.py               | typing per chat+thread, reaction per msg      |
| Heartbeat results → DM / private only       | ✅     | cli/commands.py, heartbeat/service.py                  | test_heartbeat_service.py + targeted tests | skips negative IDs and topic sub-sessions  |
| Heartbeat runs stateless by default         | ✅     | cli/commands.py, config/schema.py, agent/loop.py, heartbeat/service.py | tests/agent/test_heartbeat_service.py, tests/cli/test_commands.py | `heartbeat.keep_recent_messages = 0` |
| Heartbeat session bounded by content+tail   | ✅     | cli/commands.py, session/manager.py                    | session history regressions            | `prune_by_content_length(4000)` + keep_recent |
| Cron reminders are evaluator-biased to notify | ✅   | cli/commands.py, utils/evaluator.py                    | tests/cli/test_commands.py, tests/agent/test_evaluator.py | scheduled reminder context passed to evaluator |
| Media downloads → workspace/media/          | ✅     | channels/telegram.py                                   | tests/test_media_download.py           | falls back to `~/.nanobot/media`              |
| OpenAI compat uses `max_completion_tokens` only | ✅  | providers/openai_compat_provider.py                    | tests/providers/test_litellm_kwargs.py | no duplicate `max_tokens` field               |
| SDK retries disabled + surfaced to progress | ✅     | providers/base.py, providers/*, agent/loop.py         | tests/providers/test_provider_retry.py | provider SDK retries forced to `0`            |
| Fine-grained workspace allowlist for tools   | ✅     | config/schema.py, config/loader.py, cli/commands.py, agent/loop.py, agent/subagent.py, agent/tools/shell.py | tests/config/test_config_migration.py, tests/tools/test_exec_security.py | `restrictToWorkspace = { enabled, extraRead, extraWrite }` |
| Telegram forwarded message debounce         | ✅     | channels/telegram.py                                   | tests/channels/test_telegram_channel.py | 80ms lane = `chat_id:thread_id`              |
| **TTS voice notes (Edge + OpenAI + Riva)**  | ✅     | providers/tts.py, tts/manager.py, channels/telegram.py | tests/test_tts.py (new)                | `tts.enabled = false` (default)               |
| **/trace command - AI thinking visibility** | ✅     | channels/telegram.py                                   | tests/test_trace_command_additional.py | `_trace_enabled[chat_id] = false` (default)   |
| **/stats command - token usage visibility** | ✅     | channels/telegram.py, utils/stats.py                   | tests/test_telegram_stats_command.py   | `/stats`, `/stats topic`, `/stats all`          |
| **Commands enhanced for topic support**     | ✅     | channels/telegram.py, agent/loop.py                    | manual                                 | `/new`, `/stop`, `/model`, `/stats`, `/tts`, `/trace` |
| **Tool definitions caching (#2205)**        | ✅     | agent/tools/registry.py                                | tests/test_tool_registry_caching.py    | `_definitions_cache` invalidated on reg/unreg |
| **Incremental session saving (#2219)**      | ✅     | agent/loop.py, agent/subagent.py                       | tests/test_loop_incremental_save.py    | save offset tracks persisted content          |
| Web search enhancements merged into main   | ℹ️     | agent/tools/web.py, README.md                          | tests/tools/test_web_search_tool.py    | Multi-provider search now upstream (`brave`, `tavily`, `duckduckgo`, `searxng`, `jina`) |

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
- Automatically activates when primary model encounters provider errors including:
  - 502/503 errors (service temporarily unavailable)
  - 404 errors (model not found or unavailable)
  - 403 errors (quota exhaustion, rate limiting, access denied)
  - Timeout errors (network or server delays)
  - Invalid model errors (incorrect model specifications)
  - Provider-specific errors like "free tier exhausted" or "AllocationQuota" limits
- Transparent operation - users don't need to manually switch models
- Falls back to configured model only when specific provider errors detected
- Preserves original error if both primary and fallback models fail

**Files**
- nanobot/config/schema.py → AgentDefaults.fallback_model field
- nanobot/agent/loop.py → _run_agent_loop with enhanced try/catch logic and fallback mechanism
- nanobot/cli/commands.py → Wiring of fallback_model parameter to AgentLoop
- nanobot/agent/subagent.py → SubagentManager also supports fallback model propagation

**Resolution priority**
Preserve the enhanced try/catch wrapper around provider.chat_with_retry that checks for provider errors and attempts fallback model. The fallback logic now includes comprehensive error detection covering:
- 'provider returned error'
- '502' in error_msg
- '503' in error_msg
- 'timeout' in error_msg
- '404' in error_msg
- '403' in error_msg
- 'not found' in error_msg
- 'invalid model' in error_msg
- 'allocationquota' in error_msg (specific to quota-related errors)
- 'free tier' in error_msg (specific to your error)
- 'exhausted' in error_msg (specific to quota exhaustion)

**Quick validation**
Configure fallback_model in config and test with a temporarily unavailable primary provider or quota-exhausted model.

### 5. Provider retry plumbing and OpenAI compat request shape

**Core behavior**
- `OpenAICompatProvider` now sends only `max_completion_tokens` for OpenAI-compatible backends that reject simultaneous `max_tokens` + `max_completion_tokens`
- Native SDK retries are disabled for both `AsyncOpenAI` and `AsyncAnthropic`
- Provider retry helpers accept an `on_retry(attempt, total)` callback
- `AgentLoop` forwards retry attempts to progress sinks as `Retrying... (attempt x/y)`

**Files to protect during conflicts**
- `nanobot/providers/openai_compat_provider.py`
- `nanobot/providers/anthropic_provider.py`
- `nanobot/providers/base.py`
- `nanobot/agent/loop.py`

**Resolution priority**
Keep the SDK constructors with `max_retries=0` and explicit `httpx.Timeout(180.0, connect=10.0)`.  
Keep `OpenAICompatProvider._build_kwargs()` using `max_completion_tokens` only.  
Preserve the additive `on_retry` callback wiring in both retry helpers and the loop progress bridge.

**Quick validation**
```bash
pytest tests/providers/test_custom_provider.py tests/providers/test_litellm_kwargs.py tests/providers/test_provider_retry.py -q
```

### 6. Heartbeat session bounding

**Core behavior**
- Gateway heartbeat now reuses the stable `heartbeat` session key
- Before and after each run, heartbeat history is pruned in two dimensions:
  - `Session.prune_by_content_length(4000)` truncates oversized message text
  - `retain_recent_legal_suffix(keep_recent_messages)` keeps only a valid recent tail
- Direct-turn persistence keeps the user prompt, which is required for legal suffix trimming to work

**Files to protect during conflicts**
- `nanobot/cli/commands.py`
- `nanobot/session/manager.py`
- `nanobot/agent/loop.py`

**Resolution priority**
Keep heartbeat cleanup on the same session that `process_direct()` uses.  
Keep the direct-turn save behavior that persists the user message, not just the assistant reply.

**Quick validation**
```bash
pytest tests/agent/test_loop_save_turn.py tests/agent/test_session_manager_history.py -q
```

### 7. Heartbeat is stateless by default

**Core behavior**
- `heartbeat.keep_recent_messages` now defaults to `0`, which means heartbeat runs do not load or persist chat history
- The gateway still keeps DM-only delivery targeting and existing content-bound pruning logic when a positive `keep_recent_messages` value is configured
- `AgentLoop.process_direct(..., ephemeral_session=True)` skips session load, save, and consolidation scheduling for heartbeat-style background work
- The heartbeat service now uses an execution lock so a timer tick and manual trigger cannot overlap

**Files to protect during conflicts**
- `nanobot/config/schema.py`
- `nanobot/cli/commands.py`
- `nanobot/agent/loop.py`
- `nanobot/heartbeat/service.py`

**Resolution priority**
Keep `keep_recent_messages = 0` as the default.  
Do not regress the explicit ephemeral-session path for background runs.  
Preserve the execution lock and the more accurate active-task detection that prefers the `## Active Tasks` section.

**Quick validation**
```bash
pytest tests/agent/test_heartbeat_service.py tests/agent/test_loop_consolidation_tokens.py tests/cli/test_commands.py -q
```

### 8. Cron reminder notifications are biased toward delivery

**Core behavior**
- Cron-triggered reminder jobs now pass scheduled-reminder context into the post-run evaluator
- The evaluator prompt explicitly treats reminder/timer completions as user-visible by default
- If the message tool already delivered something during the turn, the evaluator is still bypassed as before

**Files to protect during conflicts**
- `nanobot/cli/commands.py`
- `nanobot/utils/evaluator.py`

**Resolution priority**
Keep the scheduled-reminder context string passed to `evaluate_response(...)`.  
Keep the evaluator prompt wording that treats reminder/timer completions as usually worth notifying about.

**Quick validation**
```bash
pytest tests/agent/test_evaluator.py tests/cli/test_commands.py -q
```

### 9. Telegram forwarded-message debounce

**Core behavior**
- Forwarded messages get an 80ms debounce window so Telegram’s split updates become one agent turn
- Plain text gets the same 80ms companion window to support reverse ordering (`text` then `forward`)
- Buffers are isolated per `chat_id:message_thread_id`
- Commands bypass debounce
- Non-forward media bypass debounce
- Media groups route through the same debounce path, and `stop()` cancels pending debounce tasks without flushing

**Files to protect during conflicts**
- `nanobot/channels/telegram.py`
- `tests/channels/test_telegram_channel.py`

**Resolution priority**
Preserve topic-aware lane isolation and command bypass.  
Do not regress local Telegram features such as topic routing, mention-only mode, trace, stats, TTS, or thinking placeholders while editing `_on_message()` / `_flush_media_group()`.

**Quick validation**
```bash
pytest tests/channels/test_telegram_channel.py -q
```

### 10. Fine-grained workspace allowlist for tools

**Core behavior**
- `tools.restrictToWorkspace` is now a nested object, not just a boolean
- `enabled: true` keeps file tools and shell execution restricted to the workspace by default
- `extraRead` adds extra read-only roots for `read_file`
- `extraWrite` adds extra roots that may be read, written, edited, listed, and used as valid shell working directories
- Shell guard checks now validate both absolute paths and the effective `working_dir` against the workspace plus `extraWrite`

**Files to protect during conflicts**
- `nanobot/config/schema.py`
- `nanobot/config/loader.py`
- `nanobot/cli/commands.py`
- `nanobot/agent/loop.py`
- `nanobot/agent/subagent.py`
- `nanobot/agent/tools/shell.py`
- `README.md`
- `nanobot/templates/TOOLS.md`

**Resolution priority**
Keep the nested config shape:
- `restrictToWorkspace.enabled`
- `restrictToWorkspace.extraRead`
- `restrictToWorkspace.extraWrite`

Do not regress back to a bare boolean-only config.
Do not drop the exec-side enforcement for allowed working directories, or shell commands can escape by overriding `working_dir`.

**Quick validation**
```bash
pytest tests/config/test_config_migration.py tests/tools/test_exec_security.py tests/tools/test_tool_validation.py tests/cli/test_commands.py -q
```

### 11–15. Other smaller features (summary)

- Thinking draft message → PM only (`if is_group: return`)
- Typing + ACK reaction → per composite key (chat+thread)
- Heartbeat DM-only logic lives in `_pick_heartbeat_target()` inside `nanobot/cli/commands.py` (not `heartbeat/service.py`)
- Skips topic sub-sessions and negative Telegram chat IDs
- Heartbeat history is bounded pre/post run by content length and recent legal suffix
- Media → `workspace/media/` when workspace configured

### 12. Tool definitions caching (#2205)

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

### 13. Incremental session saving (#2219)

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

### 12. Web search status after merge

**Core behavior**
- The old local-only DuckDuckGo enhancement is no longer branch-specific
- `origin/main` now includes the web search implementation in `nanobot/agent/tools/web.py`
- Upstream supports multiple providers: `brave`, `tavily`, `duckduckgo`, `searxng`, `jina`
- `duckduckgo` still uses the `ddgs` library, but this is now part of the merged baseline

**Files to protect during conflicts**
- nanobot/agent/tools/web.py
- README.md
- tests/tools/test_web_search_tool.py

**Resolution priority**
Do not treat web search as a local-only feature anymore. Keep the upstream multi-provider implementation and only document truly branch-specific behavior in this file.

**Quick validation**
```bash
pytest tests/tools/test_web_search_tool.py -q
```
