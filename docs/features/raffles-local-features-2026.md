# Branch-Specific Features – raffles/local (post-merge April 2026)

This document records features developed on `raffles/local`  
that survived the merge with `origin/main` on 13 March 2026  
and the merge with upstream/main on 2 April 2026.

Goal: help future merge conflict resolution (human or agent)  
understand intended behavior quickly.

## Feature Summary Table

| Feature                                     | Status | Primary files                                          | Key test / validation                  | Important config / default                    |
|---------------------------------------------|--------|--------------------------------------------------------|----------------------------------------|-----------------------------------------------|
| Telegram Topic support in groups            | ✅     | channels/telegram.py, cron/*, agent/tools/cron.py      | tests/test_cron_topic_delivery.py      | session_key includes `:topic:{thread_id}`     |
| Telegram groups → mention-only mode         | ✅     | channels/telegram.py                                   | manual + group_policy test             | `group_policy = "mention"` (default)          |
| Group commands via @mention                 | ✅     | channels/telegram.py → _on_message                     | manual                                 | `@BotName /command` → text message path       |
| Configured subagents via `spawn(subagent_id)` | ✅   | config/schema.py, cli/commands.py, agent/loop.py, agent/subagent.py, agent/tools/spawn.py | tests/agent/test_configured_subagents.py, tests/agent/test_task_cancel.py | named `agents.*` profiles inherit from `agents.defaults` |
| Ordered fallback models on provider errors  | ✅     | agent/loop.py, config/schema.py, cli/commands.py, agent/subagent.py | tests/agent/test_fallback_models.py, tests/config/test_config_migration.py | `fallback_models: []` (list, tried in order) |
| "Thinking…" placeholder (PM only)           | ✅     | channels/telegram.py → _send_thinking_message          | tests/test_thinking_message.py         | skipped when `is_group == True`               |
| Typing indicator & ACK reaction             | ✅     | channels/telegram.py                                   | tests/test_typing_ack.py               | typing per chat+thread, `react_emoji` can be str or list |
| Heartbeat results → DM / private only       | ✅     | cli/commands.py, heartbeat/service.py                  | test_heartbeat_service.py + targeted tests | skips negative IDs and topic sub-sessions  |
| Heartbeat runs stateless by default         | ✅     | cli/commands.py, config/schema.py, agent/loop.py, heartbeat/service.py | tests/agent/test_heartbeat_service.py, tests/cli/test_commands.py | `heartbeat.keep_recent_messages = 0` |
| Heartbeat session bounded by content+tail   | ✅     | cli/commands.py, session/manager.py                    | session history regressions            | `prune_by_content_length(4000)` + keep_recent |
| Cron reminders are evaluator-biased to notify | ✅   | cli/commands.py, utils/evaluator.py                    | tests/cli/test_commands.py, tests/agent/test_evaluator.py | scheduled reminder context passed to evaluator |
| Media downloads → workspace/media/          | ✅     | channels/telegram.py, config/paths.py                  | tests/test_media_download.py, tests/test_simple_features.py | falls back to `~/.nanobot/media` when no workspace |
| Built-in `ipinfo` skill                     | ✅     | skills/ipinfo/SKILL.md, skills/README.md               | tests/agent/test_builtin_skills.py     | requires `curl`, no API key                   |
| OpenAI compat uses `max_completion_tokens` only | ✅  | providers/openai_compat_provider.py                    | tests/providers/test_litellm_kwargs.py | no duplicate `max_tokens` field               |
| SDK retries disabled + surfaced to progress | ✅     | providers/base.py, providers/*, agent/loop.py         | tests/providers/test_provider_retry.py | provider SDK retries forced to `0`            |
| Fine-grained workspace allowlist for tools   | ✅     | config/schema.py, config/loader.py, cli/commands.py, agent/loop.py, agent/subagent.py, agent/tools/shell.py | tests/config/test_config_migration.py, tests/tools/test_exec_security.py | `restrictToWorkspace = { enabled, extraRead, extraWrite }` |
| Telegram forwarded message debounce         | ✅     | channels/telegram.py                                   | tests/channels/test_telegram_channel.py | 80ms lane = `chat_id:thread_id`              |
| **TTS voice notes (Edge + OpenAI + Riva)**  | ✅     | providers/tts.py, tts/manager.py, channels/telegram.py | tests/test_tts.py (new)                | `tts.enabled = false` (default)               |
| **/trace command - AI thinking visibility** | ✅     | channels/telegram.py                                   | tests/test_trace_command_additional.py | `_trace_enabled[chat_id] = false` (default)   |
| **/stats command - token usage visibility** | ✅     | channels/telegram.py, utils/stats.py                   | tests/test_telegram_stats_command.py   | `/stats`, `/stats topic`, `/stats all`          |
| **/status shows session model override**   | ✅     | command/builtin.py, utils/helpers.py                   | tests/cli/test_restart_command.py      | shows `gpt-4o (default: claude-opus-4)` when overridden |
| **Builtin commands preserve topic context** | ✅   | command/builtin.py, channels/telegram.py              | tests/test_telegram_builtin_commands_topic.py | `/new`, `/stop`, `/restart`, `/status`, `/help` |
| **Cron jobs preserve topic thread_id**     | ✅     | agent/loop.py, agent/tools/cron.py                    | tests/test_cron_topic_delivery.py      | thread_id passed through _run_agent_loop |
| **Subagent responses preserve topic**      | ✅     | agent/loop.py, agent/subagent.py, agent/tools/message.py | tests/test_telegram_builtin_commands_topic.py | OutboundMessage from system messages includes thread_id |
| **Telegram updater auto-restart on network errors** | ✅ | channels/telegram.py | manual | monitors updater.running, exponential backoff retry |
| **Commands enhanced for topic support**     | ✅     | channels/telegram.py, agent/loop.py                    | manual                                 | `/new`, `/stop`, `/model`, `/stats`, `/tts`, `/trace` |
| **Tool definitions caching (#2205)**        | ✅     | agent/tools/registry.py                                | tests/test_tool_registry_caching.py    | `_definitions_cache` invalidated on reg/unreg |
| **Incremental session saving (#2219)**      | ✅     | agent/loop.py, agent/subagent.py                       | tests/test_loop_incremental_save.py    | save offset tracks persisted content          |
| **Repeated tool call protection**           | ✅     | agent/runner.py, utils/runtime.py, config/schema.py    | tests/agent/test_runner.py             | `maxRepeatLookups: 2` blocks infinite loops   |
| Web search enhancements merged into main   | ℹ️     | agent/tools/web.py, README.md                          | tests/tools/test_web_search_tool.py    | Multi-provider search now upstream (`brave`, `tavily`, `duckduckgo`, `searxng`, `jina`) |
| Runtime hardening (PR #2733)               | ℹ️     | agent/runner.py, agent/hook.py, agent/loop.py          | tests/agent/test_runner.py             | Now upstream: AgentRunner, checkpoints, tool batching, provider retry |

## Detailed Descriptions & Merge Guidance

### 1. Telegram Topic support in groups + topic-aware cron

**Core behavior**
- Session key = `telegram:{chat_id}:topic:{message_thread_id}` (non-private + thread exists)
- `message_thread_id` carried in message metadata
- Cron jobs respect `threadId` field when delivering to group topics
- **thread_id preserved** when creating cron jobs via `_run_agent_loop` → `_set_tool_context`

**Files to protect during conflicts**
- nanobot/channels/telegram.py  
  → _derive_topic_session_key(), _build_message_metadata(), _on_message(), _forward_command()
- nanobot/cron/types.py, nanobot/cron/service.py
- nanobot/agent/tools/cron.py → set_context(channel, chat_id, thread_id)
- nanobot/agent/loop.py → _run_agent_loop(thread_id=...), _set_tool_context()

**Resolution priority**
Prefer version that keeps `message_thread_id` in metadata and derives session key from it.
Ensure `thread_id` is passed through `_run_agent_loop` to `_set_tool_context` so cron jobs
created from topics preserve the target thread.

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
- **Persisted** to `~/.nanobot/overrides.json` and loaded on startup

**Files**
- agent/loop.py → _model_overrides, _handle_model_command, _run_agent_loop
- config/paths.py → load_model_overrides, save_model_overrides

**Resolution priority**
Keep `_model_overrides` dict + `effective_model = model_override or self.model`.
Reset keyword is `reset` (not `default`).
Overrides persist across restarts.

### 4. Configured subagents via spawn

**Core behavior**
- Additional named entries under `agents` are treated as subagent profiles
- Non-default profiles inherit unspecified fields from `agents.defaults`
- `spawn` accepts `subagent_id` so the main agent can deliberately pick a configured subagent backend
- The spawn tool description advertises configured profiles so the main agent can discover them in-context
- This phase is intentionally limited to background subagents; it does not implement full peer-agent routing or handoff

**Files**
- `nanobot/config/schema.py` → `AgentsConfig` now preserves named agent profiles and resolves them against `defaults`
- `nanobot/cli/commands.py` → provider factory wiring for per-profile subagent providers
- `nanobot/agent/loop.py` → passes named agent config + provider factory into `SubagentManager`
- `nanobot/agent/subagent.py` → resolves selected profile, builds the matching provider, and runs the subagent with that model/settings
- `nanobot/agent/tools/spawn.py` → adds `subagent_id` parameter and dynamic profile advertising

**Resolution priority**
Keep named agent profiles as overlays on `agents.defaults`, not fully separate standalone configs.  
Keep the scope limited to `spawn(subagent_id=...)`. Do not conflate this with the larger multi-agent work from PR #2064.  
Preserve the existing default subagent path when no `subagent_id` is provided.

**Quick validation**
```bash
pytest tests/agent/test_configured_subagents.py tests/agent/test_task_cancel.py tests/config/test_config_migration.py tests/cli/test_commands.py -q
```

### 5. Ordered fallback models on provider errors

**Core behavior**
- Configure `fallback_models` as an ordered list of models to try when the primary fails
- Models are tried in the order they appear in the list
- The runtime de-duplicates the chain, so repeated model names are skipped automatically
- Automatically activates when the primary model encounters provider errors including:
  - 502/503 errors (service temporarily unavailable)
  - 404 errors (model not found or unavailable)
  - 403 errors (quota exhaustion, rate limiting, access denied)
  - Timeout errors (network or server delays)
  - Invalid model errors (incorrect model specifications)
  - Provider-specific errors like "free tier exhausted" or "AllocationQuota" limits
- Transparent operation - users don't need to manually switch models
- Falls back only when specific provider errors are detected
- Preserves the original primary error if the whole fallback chain fails

**Files**
- nanobot/config/schema.py → AgentDefaults.fallback_models (list[str])
- nanobot/agent/loop.py → ordered fallback chain helper + loop-level failover execution
- nanobot/cli/commands.py → wiring of fallback_models to AgentLoop
- nanobot/agent/subagent.py → SubagentManager keeps the same fallback config surface

**Resolution priority**
Preserve the loop-level fallback helper that tries the ordered chain and keeps the branch's broader provider-error detection. The fallback trigger list includes:
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

Keep the list-based fallback config:
- `fallback_models` is a list of model names tried in order
- Skip duplicates and skip the already-selected primary model

**Config example**
```json
{
  "agents": {
    "defaults": {
      "fallbackModels": ["openai/gpt-4o", "anthropic/claude-3-sonnet"]
    }
  }
}
```

**Quick validation**
```bash
pytest tests/agent/test_fallback_models.py tests/config/test_config_migration.py tests/cli/test_commands.py -q
```

### 6. Provider retry plumbing and OpenAI compat request shape

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

### 7. Heartbeat session bounding

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

### 8. Heartbeat is stateless by default

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

### 9. Cron reminder notifications are biased toward delivery

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

### 10. Telegram forwarded-message debounce

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

### 11. Configurable ACK reaction emoji

**Core behavior**
- `react_emoji` config now accepts both string and list formats
- String `"👀"` → always use that fixed emoji
- List `["⚡️", "👌", "👀"]` → randomly pick from list on each message
- Single-item list `["🔥"]` → always use that emoji
- Empty string `""` or empty list `[]` → disable ACK reaction entirely
- Default: `["⚡️", "👌", "👀", "🔥", "👍"]` (matches previous random behavior)

**Files to protect during conflicts**
- `nanobot/config/schema.py` → TelegramConfig.react_emoji field
- `nanobot/channels/telegram.py` → `_pick_react_emoji()`, `_add_ack_reaction()`

**Resolution priority**
Keep the union type `str | list[str]` for backward compatibility.  
Preserve the helper method that normalizes string vs list selection.

**Config example**
```json
{
  "channels": {
    "telegram": {
      "reactEmoji": ["⚡️", "👌", "👀"]
    }
  }
}
```

**Quick validation**
```bash
pytest tests/test_typing_ack.py tests/channels/test_telegram_config_loading.py -q
```

### 12. Fine-grained workspace allowlist for tools

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

### 13. Built-in ipinfo skill

**Core behavior**
- Adds a built-in `ipinfo` skill for public IP and coarse geolocation lookup
- Uses only free HTTP endpoints and `curl`; no API key or extra packages are required
- Documents a simple fallback sequence across `ipinfo.io`, `ipify`, and `ipwho.is`

**Files**
- `nanobot/skills/ipinfo/SKILL.md`
- `nanobot/skills/README.md`

**Resolution priority**
Keep the skill in English and dependency-light.  
Do not expand this phase into runtime code changes or new tool integrations.

**Quick validation**
```bash
pytest tests/agent/test_builtin_skills.py -q
```

### 14. /status shows session model override

**Core behavior**
- `/status` command now displays the effective model for the current session
- When a model override is set via `/model <model-id>`, status shows both the override and the default
- Format: `🧠 Model: gpt-4o (default: anthropic/claude-opus-4-5)` when overridden
- Format: `🧠 Model: anthropic/claude-opus-4-5` when using default

**Files to protect during conflicts**
- nanobot/command/builtin.py → cmd_status passes model_override to build_status_content
- nanobot/utils/helpers.py → build_status_content accepts and displays model_override parameter

**Resolution priority**
Keep the model_override parameter flowing from `loop._model_overrides.get(session_key)` through to the status output.

**Quick validation**
```bash
pytest tests/cli/test_restart_command.py::TestRestartCommand::test_status_shows_model_override -v
```

### 15. Builtin commands preserve topic context

**Core behavior**
- `/new`, `/stop`, `/restart`, `/status`, `/help` commands preserve `message_thread_id` in metadata
- Ensures replies stay in the correct topic thread
- Fixes bug where commands sent from topics would respond to main chat instead

**Files to protect during conflicts**
- nanobot/command/builtin.py → cmd_stop, cmd_restart, cmd_status, cmd_new, cmd_help
- Each command includes `metadata = {"message_thread_id": ctx.msg.metadata.get("message_thread_id")}`

**Resolution priority**
Keep the `message_thread_id` extraction and inclusion in outbound metadata for all builtin commands.

**Quick validation**
```bash
pytest tests/test_telegram_builtin_commands_topic.py -v
```

### 16–20. Other smaller features (summary)

- Thinking draft message → PM only (`if is_group: return`)
- Typing + ACK reaction → per composite key (chat+thread)
- `react_emoji` config → string for fixed emoji, list for random selection from pool, empty string/list to disable
- Media downloads → `workspace/media/telegram/` when workspace is configured (accessible within workspace restrictions)
- Telegram flood control retry → handles `RetryAfter` errors with automatic retry
- Model/TTS overrides → persisted to `~/.nanobot/overrides.json`, loaded on startup
- Cron thread_id → preserved through `_run_agent_loop` for topic-aware job creation
- Heartbeat DM-only logic lives in `_pick_heartbeat_target()` inside `nanobot/cli/commands.py` (not `heartbeat/service.py`)
- Skips topic sub-sessions and negative Telegram chat IDs
- Heartbeat history is bounded pre/post run by content length and recent legal suffix

### 17. Tool definitions caching (#2205)

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

### 18. Incremental session saving (#2219)

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

### 19. Repeated tool call protection (infinite loop prevention)

**Core behavior**
- Prevents models from getting stuck in infinite tool-calling loops (e.g., repeatedly reading the same file)
- Blocks repeated calls to `read_file`, `web_fetch`, and `web_search` with identical arguments after a configurable threshold
- Default threshold: 2 (allows 2 retries, blocks on 3rd attempt)
- Configurable via `agents.defaults.maxRepeatLookups` in config
- When blocked, model receives error message forcing it to use existing results

**Root cause of original bug**
- Model `infini-minimax-m27` got stuck reading `SESSION-STATE.md` 30+ times without producing output
- AGENTS.md had aggressive instruction: "Check SESSION-STATE.md on EVERY message"
- Existing detection only covered `web_fetch` and `web_search`, not `read_file`
- Model followed instruction literally but couldn't break out of the loop

**Files to protect during conflicts**
- nanobot/utils/runtime.py → `external_lookup_signature()` (now includes `read_file`), `repeated_external_lookup_error()`
- nanobot/agent/runner.py → `AgentRunSpec.max_repeat_lookups`, passes to `repeated_external_lookup_error()`
- nanobot/agent/loop.py → `max_repeat_lookups` param, passes to `AgentRunSpec` and `SubagentManager`
- nanobot/agent/subagent.py → `max_repeat_lookups` param
- nanobot/cli/commands.py → wires config to `AgentLoop` (3 places)
- nanobot/config/schema.py → `AgentDefaults.max_repeat_lookups` field

**Resolution priority**
1. Keep `read_file` in `external_lookup_signature()` - this is the key fix for the infinite loop
2. Keep the configurable `max_repeat_lookups` parameter flowing through the call chain
3. Keep the error message that forces the model to proceed with existing results

**Config example**
```json
{
  "agents": {
    "defaults": {
      "maxRepeatLookups": 2
    }
  }
}
```

**AGENTS.md guidance** (should also be updated)
```markdown
5. **Read `SESSION-STATE.md` ONCE per turn** — at the START of processing a new user message

**WAL Protocol:**
- Read SESSION-STATE.md once at the start of your response
- DO NOT read it again in the same turn
- If you already read a file this turn, proceed to respond — don't re-read
```

**Quick validation**
```bash
# Check that repeated read_file calls are blocked after threshold
pytest tests/agent/test_runner.py -v
```

### 20. Subagent responses preserve topic thread_id

**Core behavior**
- When a subagent announces its result via system message, the response goes to the correct topic
- System message processing extracts `message_thread_id` from metadata and builds topic-scoped session key
- `OutboundMessage` returned from system message processing includes `thread_id` in metadata
- MessageTool preserves `thread_id` when LLM explicitly provides `channel` and `chat_id` parameters

**Root cause of original bug**
- Subagent `_announce_result()` was correctly setting `metadata["message_thread_id"]`
- System message processing was building correct session key with topic
- BUT `OutboundMessage` returned at end of system message processing was NOT including `thread_id` in metadata
- This caused the final response to go to General instead of the topic

**Files to protect during conflicts**
- nanobot/agent/loop.py → `_process_message()` for system messages, metadata in OutboundMessage
- nanobot/agent/subagent.py → `_announce_result()` includes `message_thread_id` in metadata
- nanobot/agent/tools/message.py → `execute()` preserves `thread_id` when `same_target` is True

**Resolution priority**
1. Keep `metadata["message_thread_id"]` in subagent's `_announce_result()`
2. Keep thread_id extraction in system message processing: `thread_id = msg.metadata.get("message_thread_id")`
3. Keep topic-scoped session key: `key = f"{channel}:{chat_id}:topic:{thread_id}"`
4. **CRITICAL**: Keep `thread_id` in OutboundMessage metadata for system message responses
5. Keep MessageTool's `same_target` logic that preserves thread_id

**Quick validation**
```bash
pytest tests/test_telegram_builtin_commands_topic.py tests/test_cron_topic_delivery.py -v
```

### 21. Telegram updater auto-restart on network errors

**Core behavior**
- Monitors `updater.running` state in the polling loop
- If updater stops unexpectedly (network error, DNS failure), auto-restarts with exponential backoff
- Retry delay: 5s → 7.5s → 11.25s → ... → 60s max
- Resets retry delay on successful restart
- Preserves all bot context (sessions, memory, handlers, Application state)

**Network errors handled**
- DNS resolution failures (`Temporary failure in name resolution`)
- Bad Gateway (502)
- Service Unavailable (503)
- Connection timeouts
- General `NetworkError` from python-telegram-bot

**Important**: This restarts only the **polling task**, not the entire bot:
- `updater.start_polling()` starts a background coroutine that polls `getUpdates()` API
- When network errors occur, this internal task stops and `updater.running` becomes `False`
- The fix simply calls `updater.start_polling()` again on the same Application
- All state (sessions, memory, handlers, caches) is preserved

**Files to protect during conflicts**
- nanobot/channels/telegram.py → `start()` method, polling loop with `updater.running` check

**Resolution priority**
Keep the monitoring loop that checks `updater.running` and restarts polling.
Do NOT restart the entire Application - that would wipe context.

**Code pattern**
```python
while self._running:
    await asyncio.sleep(1)
    if self._running and not self._app.updater.running:
        await asyncio.sleep(retry_delay)
        await self._app.updater.start_polling(...)
        retry_delay = 5.0  # reset on success
```

### 22. Web search status after merge

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
