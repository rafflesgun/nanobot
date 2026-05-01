# Branch-Specific Features – raffles/local (post-merge April 2026)

This document records features developed on `raffles/local`  
that survived the merge with `origin/main` on 13 March 2026  
the merge with upstream/main on 2 April 2026,
and the merge with `origin/main` on 27 April 2026,
and the merge with `upstream/main` on 1 May 2026.

Goal: help future merge conflict resolution (human or agent)  
understand intended behavior quickly.

## Feature Summary Table

| Feature                                     | Status | Primary files                                          | Key test / validation                  | Important config / default                    |
|---------------------------------------------|--------|--------------------------------------------------------|----------------------------------------|-----------------------------------------------|
| Telegram Topic support in groups            | ✅     | channels/telegram.py, cron/*, agent/tools/cron.py      | tests/test_cron_topic_delivery.py      | session_key includes `:topic:{thread_id}`     |
| Telegram groups → mention-only mode         | ✅     | channels/telegram.py                                   | manual + group_policy test             | `group_policy = "mention"` (default)          |
| Group commands via @mention                 | ✅     | channels/telegram.py → _on_message                     | manual                                 | `@BotName /command` → text message path       |
| Configured subagents via `spawn(subagent_id)` | ✅   | config/schema.py, cli/commands.py, agent/loop.py, agent/subagent.py, agent/tools/spawn.py | tests/agent/test_configured_subagents.py, tests/agent/test_task_cancel.py | named `agents.*` profiles inherit from `agents.defaults` |
| Ordered fallback models on provider errors  | ✅     | agent/loop.py, config/schema.py, cli/commands.py, agent/subagent.py | tests/agent/test_fallback_models.py, tests/config/test_config_migration.py | `fallback_models: []` (list, tried in order, includes bare `429` and plain `temporarily unavailable`) |
| "Thinking…" placeholder (PM only)           | ✅     | channels/telegram.py → _send_thinking_message          | tests/test_thinking_message.py         | skipped when `is_group == True`               |
| Typing indicator & ACK reaction             | ✅     | channels/telegram.py                                   | tests/test_typing_ack.py               | typing per chat+thread, `react_emoji` can be str or list |
| Heartbeat results → DM / private only       | ✅     | cli/commands.py, heartbeat/service.py                  | test_heartbeat_service.py + targeted tests | skips negative IDs and topic sub-sessions  |
| Heartbeat runs stateless by default         | ✅     | cli/commands.py, config/schema.py, agent/loop.py, heartbeat/service.py | tests/agent/test_heartbeat_service.py, tests/cli/test_commands.py | `heartbeat.keep_recent_messages = 0` |
| Heartbeat session bounded by content+tail   | ✅     | cli/commands.py, session/manager.py                    | session history regressions            | `prune_by_content_length(4000)` + keep_recent |
| Cron reminders are evaluator-biased to notify | ✅   | cli/commands.py, utils/evaluator.py                    | tests/cli/test_commands.py, tests/agent/test_evaluator.py | scheduled reminder context passed to evaluator |
| Media downloads → workspace/media/          | ✅     | channels/telegram.py, config/paths.py                  | tests/test_media_download.py, tests/test_simple_features.py | falls back to `~/.nanobot/media` when no workspace |
| Built-in `ipinfo` skill                     | ✅     | skills/ipinfo/SKILL.md, skills/README.md               | tests/agent/test_builtin_skills.py     | requires `curl`, no API key                   |
| OpenAI compat uses `max_completion_tokens` only | ✅  | providers/openai_compat_provider.py                    | tests/providers/test_litellm_kwargs.py | no duplicate `max_tokens` field               |
| SDK retries disabled + surfaced to progress | ✅     | providers/base.py, providers/*, agent/loop.py         | tests/providers/test_provider_retry.py, tests/agent/test_task_cancel.py | provider SDK retries forced to `0`; retry logs include request id/model/inflight and agent gate occupancy |
| Fine-grained workspace allowlist for tools   | ✅     | config/schema.py, config/loader.py, cli/commands.py, agent/loop.py, agent/subagent.py, agent/tools/shell.py | tests/config/test_config_migration.py, tests/tools/test_exec_security.py | `restrictToWorkspace = { enabled, extraRead, extraWrite }` |
| Telegram forwarded message debounce         | ✅     | channels/telegram.py                                   | tests/channels/test_telegram_channel.py | 80ms lane = `chat_id:thread_id`              |
| **TTS voice notes (Edge + OpenAI + Riva)**  | ✅     | providers/tts.py, tts/manager.py, channels/telegram.py, utils/audio.py | tests/test_tts.py (new)                | `tts.enabled = false` (default), text sent before TTS, 30s timeout, overrides persist across restart |
| **/trace command - AI thinking visibility** | ✅     | channels/telegram.py                                   | tests/test_trace_command_additional.py | `_trace_enabled[chat_id] = false` (default, chat-scoped not topic-scoped) |
| **/stats command - token usage visibility** | ✅     | channels/telegram.py, utils/stats.py                   | tests/test_telegram_stats_command.py   | `/stats`, `/stats topic`, `/stats all`          |
| **/status shows session model override**   | ✅     | command/builtin.py, utils/helpers.py                   | tests/cli/test_restart_command.py      | shows `gpt-4o (default: claude-opus-4)` when overridden |
| **Builtin commands preserve topic context** | ✅   | command/builtin.py, channels/telegram.py              | tests/test_telegram_builtin_commands_topic.py | `/new`, `/stop`, `/restart`, `/status`, `/help` |
| **Channel Info includes Telegram thread_id** | ✅  | agent/context.py, agent/loop.py                       | tests/agent/test_context_prompt_cache.py, tests/agent/test_loop_save_turn.py | Telegram runtime block shows `Thread ID` above `Chat ID`; non-topic = `0` |
| **Cron jobs preserve topic thread_id**     | ✅     | agent/loop.py, agent/tools/cron.py                    | tests/test_cron_topic_delivery.py      | thread_id passed through _run_agent_loop |
| **Subagent responses preserve topic**      | ✅     | agent/loop.py, agent/subagent.py, agent/tools/message.py | tests/test_telegram_builtin_commands_topic.py | OutboundMessage from system messages includes thread_id |
| **Agent runtime context exposes topic Thread ID** | ✅ | agent/context.py, agent/loop.py | tests/agent/test_context_prompt_cache.py | Runtime context includes `Channel`, `Chat ID`, and `Thread ID` for topic messages |
| **Telegram updater auto-restart on network errors** | ✅ | channels/telegram.py | manual | monitors updater.running, exponential backoff retry |
| **Commands enhanced for topic support**     | ✅     | channels/telegram.py, agent/loop.py                    | manual                                 | `/new`, `/stop`, `/model`, `/stats`, `/tts`, `/trace` |
| **Tool definitions caching (#2205)**        | ✅     | agent/tools/registry.py                                | tests/test_tool_registry_caching.py    | `_definitions_cache` invalidated on reg/unreg |
| **Incremental session saving (#2219)**      | ✅     | agent/loop.py, agent/subagent.py                       | tests/test_loop_incremental_save.py    | save offset tracks persisted content          |
| **Repeated tool call protection**           | ✅     | agent/runner.py, utils/runtime.py, config/schema.py    | tests/agent/test_runner.py             | `maxRepeatLookups: 2` blocks infinite loops   |
| **Learning loop upgrades (recall + reviewable skills)** | ✅ | session/search.py, agent/tools/session_search.py, agent/skills_manager.py, agent/tools/skill_manage.py, agent/skill_proposals.py, agent/memory.py, command/builtin.py | tests/agent/test_session_search.py, tests/tools/test_session_search_tool.py, tests/command/test_builtin_recall.py, tests/agent/test_skills_manager.py, tests/tools/test_skill_manage_tool.py, tests/agent/test_skill_proposals.py, tests/agent/test_dream.py | `/recall` excludes current session by default; Dream writes proposals to `memory/skill-proposals/`; `skill_manage` mutates workspace skills only |
| **Skill Scan v1 for workspace skill mutations** | ✅ | skills/scan.py, agent/skills_manager.py, agent/tools/skill_manage.py | tests/skills/test_scan.py, tests/agent/test_skills_manager.py, tests/tools/test_skill_manage_tool.py, tests/agent/test_skill_proposals.py, tests/agent/test_dream.py | `safe` allows writes; `warn` allows writes with findings; `block` rejects create/replace/patch/apply_proposal |
| **`nanobot doctor` deployment diagnostics** | ✅ | doctor/types.py, doctor/service.py, doctor/checks/*.py, cli/commands.py | tests/doctor/*.py, tests/cli/test_commands.py | `nanobot doctor` local checks by default; `--live` adds bounded provider/MCP probes; `--json` for scripting; exit 1 on failures |
| **Proposal metadata index + doctor drift visibility** | ✅ | agent/skill_proposal_metadata.py, agent/skill_proposals.py, agent/tools/skill_manage.py, doctor/checks/skills.py | tests/agent/test_skill_proposal_metadata.py, tests/agent/test_skill_proposals.py, tests/tools/test_skill_manage_tool.py, tests/doctor/test_skill_checks.py | Metadata index tracks `pending`/`applied`/`rejected`; doctor reports proposal health and drift |
| **OpenAI-compatible image generation tool** | ✅ | image_generation.py, agent/tools/image_generation.py, agent/loop.py, cli/commands.py, config/schema.py | tests/test_image_generation_*.py, tests/tools/test_image_generation_tool.py, tests/agent/test_loop_tool_context.py | `tools.imageGeneration.enabled = false`; gateway-only tool registration; uses `providers.openai` or `providers.custom` |
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
- The parent session `model_override` now propagates into spawned subagents unless the caller leaves it unset
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
Preserve propagation of the parent session model override into spawned subagents.

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
- Emits debug logs for the ordered fallback chain and names the next fallback model when a switch happens

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
- 'temporarily unavailable' in error_msg
- 'timeout' in error_msg
- '404' in error_msg
- '403' in error_msg
- '429' in error_msg
- 'not found' in error_msg
- 'invalid model' in error_msg
- 'allocationquota' in error_msg (specific to quota-related errors)
- 'free tier' in error_msg (specific to your error)
- 'exhausted' in error_msg (specific to quota exhaustion)

Keep the list-based fallback config:
- `fallback_models` is a list of model names tried in order
- Skip duplicates and skip the already-selected primary model
- The effective primary model is `model_override` when present, otherwise the configured default model
- Keep the debug logs that show the ordered fallback chain and the next fallback model selected after an eligible failure

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
- Provider retry diagnostics log request start/end with request id, model, streaming flag, retry mode, and provider in-flight request count
- Provider retry warnings include request id, model, and provider in-flight request count so account-level concurrency failures are visible in logs
- Agent dispatch logs include semaphore occupancy as `active=<n>/<limit>` when entering and leaving the top-level concurrency gate

**Files to protect during conflicts**
- `nanobot/providers/openai_compat_provider.py`
- `nanobot/providers/anthropic_provider.py`
- `nanobot/providers/base.py`
- `nanobot/agent/loop.py`

**Resolution priority**
Keep the SDK constructors with `max_retries=0` and explicit `httpx.Timeout(180.0, connect=10.0)`.  
Keep `OpenAICompatProvider._build_kwargs()` using `max_completion_tokens` only.  
Preserve the additive `on_retry` callback wiring in both retry helpers and the loop progress bridge.
Preserve the provider in-flight diagnostics and request ids in `LLMProvider.chat_with_retry()` / `chat_stream_with_retry()`.  
Preserve the agent concurrency-gate occupancy logs in `AgentLoop._dispatch()`.

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

### 16. Channel Info includes Telegram thread_id

**Core behavior**
- Runtime Channel Info includes `Thread ID` for Telegram sessions
- `Thread ID` appears above `Chat ID` in the runtime block
- Non-topic Telegram chats use `Thread ID: 0`
- Non-Telegram channels keep the existing runtime block without `Thread ID`

**Files to protect during conflicts**
- `nanobot/agent/context.py`
- `nanobot/agent/loop.py`

**Resolution priority**
Keep the Telegram-only runtime context branch that injects `Thread ID` before `Chat ID`.
Preserve `thread_id=0` as a real Telegram value for non-topic chats instead of treating it as missing.
Do not add `Thread ID` to non-Telegram channels.

**Quick validation**
```bash
pytest tests/agent/test_context_prompt_cache.py tests/agent/test_loop_save_turn.py -q
```

### 17–21. Other smaller features (summary)

- Thinking draft message → PM only (`if is_group: return`)
- Typing + ACK reaction → per composite key (chat+thread)
- `react_emoji` config → string for fixed emoji, list for random selection from pool, empty string/list to disable
- Media downloads → `workspace/media/telegram/` when workspace is configured (accessible within workspace restrictions)
- Telegram flood control retry → handles `RetryAfter` errors with automatic retry
- Model/TTS overrides → persisted to `~/.nanobot/overrides.json`, loaded on startup
- Temperature overrides → persisted to `~/.nanobot/overrides.json`, loaded on startup
- Cron thread_id → preserved through `_run_agent_loop` for topic-aware job creation
- Agent runtime context for topic messages includes `Thread ID: ...` so the model can see the topic identity directly
- Heartbeat DM-only logic lives in `_pick_heartbeat_target()` inside `nanobot/cli/commands.py` (not `heartbeat/service.py`)
- Skips topic sub-sessions and negative Telegram chat IDs
- Heartbeat history is bounded pre/post run by content length and recent legal suffix

### 18. TTS reliability fixes

**Core behavior**
- Text response sent **before** TTS generation so user always sees a response
- TTS generation has 30-second timeout to prevent blocking indefinitely
- Pydub/ffmpeg work runs in thread executor to avoid blocking event loop
- If TTS times out or fails, user still has the text response

**Root cause of original bug**
- TTS generation could hang or take very long
- Text was sent **after** TTS, so if TTS failed/hung, user got no response at all
- Pydub's blocking I/O was running on the main event loop, causing stalls

**Files to protect during conflicts**
- nanobot/channels/telegram.py → `send()` method: text sent before `_maybe_send_tts()`
- nanobot/channels/telegram.py → `_maybe_send_tts()`: 30s `asyncio.wait_for()` timeout
- nanobot/utils/audio.py → `_blocking_convert_to_ogg_opus()`, `_blocking_get_audio_duration()`
- nanobot/utils/audio.py → `run_in_executor()` for pydub work

**Resolution priority**
1. Keep text send BEFORE `_maybe_send_tts()` call - critical for reliability
2. Keep 30s timeout on TTS generation
3. Keep pydub work in thread executor (not blocking event loop)

**Code pattern (telegram.py send method)**
```python
# Send text content first so the user always gets a response
if msg.content and msg.content != "[empty message]":
    for chunk in split_message(msg.content, TELEGRAM_MAX_MESSAGE_LEN):
        await self._send_text(chat_id, chunk, reply_params, thread_kwargs)

await self._maybe_send_tts(...)  # TTS after text
```

**Code pattern (TTS timeout)**
```python
try:
    ogg_bytes = await asyncio.wait_for(
        temp_tts_manager.generate_voice_note(text),
        timeout=30.0,
    )
except asyncio.TimeoutError:
    logger.warning("TTS generation timed out after 30s → skipping voice note")
    return
```

### 19. Tool definitions caching (#2205)

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

### 20. Incremental session saving (#2219)

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

### 21. Repeated tool call protection (infinite loop prevention)

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

### 22. Subagent responses preserve topic thread_id

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

### 23. Telegram updater auto-restart on network errors

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

### 24. Web search status after merge

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

### 25. Kimi K2 tool call parsing (special token format)

**Core behavior**
- Parses Kimi K2's special tool call tokens when API doesn't properly format them as standard `tool_calls`
- Handles both streaming and non-streaming responses
- Strips special tokens from content after parsing to prevent them appearing in output
- Works with MiniMax and other providers that may use Kimi K2 style formatting

**Root cause**
- Kimi K2 emits tool calls using special tokens: `<|tool_calls_section_begin|>`, `<|tool_call_begin|>`, etc.
- Some API endpoints (Moonshot, vLLM, OpenRouter, MiniMax) don't always parse these into the standard OpenAI `tool_calls` field
- The raw tokens appear in the response content instead of being parsed
- GitHub issue: https://github.com/MoonshotAI/Kimi-K2/issues/89

**Special token format**
```
<|tool_calls_section_begin|>
<|tool_call_begin|>functions.func_name:0<|tool_call_argument_begin|>{"arg": "value"}<|tool_call_end|>
<|tool_calls_section_end|>
```

**Files to protect during conflicts**
- nanobot/providers/openai_compat_provider.py → `_parse_kimi_tool_calls()`, `_strip_kimi_tool_call_tokens()`, `_parse()` and `_parse_chunks()` methods

**Resolution priority**
1. Keep the Kimi K2 token parsing functions
2. Keep the calls to parsing in `_parse()` (dict path) and `_parse()` (SDK path) and `_parse_chunks()`
3. Keep the content stripping after successful parsing

**Quick validation**
```bash
python3 -c "
from nanobot.providers.openai_compat_provider import _parse_kimi_tool_calls
test = '<|tool_calls_section_begin|><|tool_call_begin|>functions.web_fetch:0<|tool_call_argument_begin|>{\"url\": \"https://example.com\"}<|tool_call_end|><|tool_calls_section_end|>'
print(len(_parse_kimi_tool_calls(test)), 'tool calls parsed')
"
```

### 26. Temperature override per session (`/model temp`)

**Core behavior**
- `/model temp` — Shows current temperature setting with guidance table
- `/model temp 0.7` — Sets temperature override for the current session
- `/model temp reset` — Clears temperature override, reverts to model default
- Temperature persists per session (like model overrides)
- Passed through to AgentRunSpec for LLM calls
- Topic sessions preserve their own temperature override independently via topic-scoped session keys

**Temperature guidance**
| Task | Recommended Temp | Why? |
|------|-----------------|------|
| Stock Analysis | 0.0 - 0.2 | Precision, factual accuracy |
| Coding / Technical | 0.2 - 0.4 | Deterministic, consistent |
| General Chat | 0.7 | Balanced creativity |
| Brainstorming | 0.9 - 1.2 | Maximum creativity |

**Implementation**
- `nanobot/config/paths.py`: Added `load_temperature_overrides()` and `save_temperature_overrides()`
- `nanobot/agent/loop.py`: Added `_temperature_overrides` dict and `_handle_temp_command()` method
- `nanobot/command/builtin.py`: Updated help text to include temperature commands

**Persistence**
- Stored in `~/.nanobot/overrides.json` alongside model and TTS overrides
- Keyed by session_key (e.g., `telegram:123456789:topic:42`)

### 27. Learning loop upgrades: session recall + reviewable skills

**Core behavior**
- `/recall <query>` searches prior session transcripts for related work and excludes the current session by default
- The agent also gets a read-only `session_search` tool that returns compact excerpts from matching prior sessions
- Binary and non-UTF-8 session files are gracefully skipped (no crash on `UnicodeDecodeError`)
- Multi-part content (list of text blocks) in agent messages is correctly extracted and searchable
- `skill_manage` provides safe workspace-only mutations for skills: create, replace, patch, delete, apply proposal, reject proposal
- Built-in skills remain read-only; only `workspace/skills/` is mutable
- Dream no longer writes skills directly into `workspace/skills/`
- Dream now writes reviewable proposals into `workspace/memory/skill-proposals/`
- Proposal files use skill-compatible frontmatter/body so they can be promoted without translation

**Files to protect during conflicts**
- `nanobot/session/search.py`
- `nanobot/agent/tools/session_search.py`
- `nanobot/agent/skills_manager.py`
- `nanobot/agent/tools/skill_manage.py`
- `nanobot/agent/skill_proposals.py`
- `nanobot/agent/memory.py`
- `nanobot/templates/agent/dream_phase2.md`
- `nanobot/command/builtin.py`

**Resolution priority**
1. Keep `/recall` as prior-session recall, not current-session search.
2. Keep `session_search` read-only and dependency-light (scan-based JSONL recall in this branch).
3. Keep `skill_manage` limited to workspace-local skills; do not allow mutation of bundled skills.
4. Keep Dream proposal-based: `memory/skill-proposals/<name>.md`, not direct writes to `skills/<name>/SKILL.md`.
5. Keep proposal promotion explicit via `apply_proposal` / `reject_proposal` instead of silent installation.

**Quick validation**
```bash
pytest tests/agent/test_session_search.py tests/tools/test_session_search_tool.py tests/command/test_builtin_recall.py tests/agent/test_skills_manager.py tests/tools/test_skill_manage_tool.py tests/agent/test_skill_proposals.py tests/agent/test_dream.py -q
```

### 28. Skill Scan v1 for workspace skill mutations

**Core behavior**
- `scan_skill_content()` classifies workspace skill text as `safe`, `warn`, or `block` before mutation writes happen
- v1 coverage is intentionally regex-based and targets six classes of risky content:
  - environment secret exfiltration via `curl ... $ENV_VAR` or `curl ... ${ENV_VAR}` (braced form)
  - prompt-injection language such as `ignore previous instructions`
  - destructive shell patterns such as `rm -rf`
  - obfuscated execution via `-c` flag (`bash -c`, `python -c`, `sh -c`, `perl -c`, `ruby -c`, `node -c`)
  - persistence via `crontab`
  - piped obfuscation via `base64 -d` or `echo ... | (bash|sh|python|perl|ruby|node)`
- `critical` and `high` findings become `block`; `medium` findings become `warn`; no findings returns `safe`

**Enforcement points**
- `SkillsManager.create()` scans full content before first write to `workspace/skills/<name>/SKILL.md`
- `SkillsManager.replace()` scans full replacement content before overwriting an existing skill
- `SkillsManager.patch()` scans the post-patch result before the atomic write, so partial edits cannot bypass the scanner
- `SkillManageTool.execute(action="apply_proposal")` enforces the same path by loading proposal content and routing it through `SkillsManager.create()` before proposal promotion

**Verdict semantics**
- `safe`: mutation succeeds and the returned JSON includes `scan: {"verdict": "safe"}`
- `warn`: mutation still succeeds, but findings are surfaced to the caller in the returned `scan` payload for review/logging
- `block`: mutation fails with `success: false`, error `Skill content blocked by safety scan`, and the structured findings payload

**Verification coverage**
- `tests/skills/test_scan.py` locks the scanner verdicts and pattern coverage
- `tests/agent/test_skills_manager.py` verifies `create`, `replace`, and `patch` reject blocked content and preserve scan payloads
- `tests/tools/test_skill_manage_tool.py` verifies tool-level JSON responses include scan results and proposal application inherits enforcement
- `tests/agent/test_skill_proposals.py` and `tests/agent/test_dream.py` cover the proposal workflow that now terminates in the same guarded mutation path

**Files to protect during conflicts**
- `nanobot/skills/scan.py`
- `nanobot/agent/skills_manager.py`
- `nanobot/agent/tools/skill_manage.py`
- `tests/skills/test_scan.py`
- `tests/agent/test_skills_manager.py`
- `tests/tools/test_skill_manage_tool.py`
- `tests/agent/test_skill_proposals.py`
- `tests/agent/test_dream.py`

**Resolution priority**
1. Keep all four mutation entry points (`create`, `replace`, `patch`, `apply_proposal`) on the scan-before-write path.
2. Keep `warn` as non-blocking; only `critical`/`high` findings should reject writes in v1.
3. Keep the scan payload in successful and blocked results so callers can inspect findings without re-running a scan.
4. Keep proposal promotion routed through `SkillsManager` instead of direct file writes, or proposal installs will bypass the contract.

**Quick validation**
```bash
python3 -m pytest tests/skills/test_scan.py tests/agent/test_skills_manager.py tests/tools/test_skill_manage_tool.py tests/agent/test_skill_proposals.py tests/agent/test_dream.py -q
```

### 29. `nanobot doctor` deployment diagnostics

**Core behavior**
- `nanobot doctor` runs fast, deterministic, read-only checks for deployment readiness
- `nanobot doctor --live` adds bounded provider auth and MCP connectivity probes
- `nanobot doctor --json` produces machine-readable output for scripting
- Exit code 1 when any check fails; warnings alone do not fail
- Designed for `docker exec <container> nanobot doctor` as the primary operator workflow

**Check coverage**
- Config: existence, JSON parsing, schema validation, env-var resolution
- Workspace: existence, writability, runtime subdirectory readiness
- Providers: default provider config presence, optional live auth/reachability probe
- Channels: required config fields for enabled channels only
- Dream: memory dir, skill proposal dir, `.dream_cursor` parent
- Skills: workspace skills and proposal directory readiness, blocked/warning proposal detection via `last_scan_verdict`
- MCP: config block shape, enabled-tools sanity, optional live connectivity probe

**Files to protect during conflicts**
- `nanobot/doctor/types.py`
- `nanobot/doctor/service.py`
- `nanobot/doctor/checks/*.py`
- `nanobot/cli/commands.py` (the `doctor` command block)

**Resolution priority**
1. Keep live probe failures as real `fail` results, not warnings.
2. Keep the MCP live probe bounded by an explicit timeout.
3. Keep the workspace skill-proposals check pointing at the real runtime path `memory/skill-proposals`, not a flat `skill_proposals` directory.
4. Keep the CLI thin: `DoctorService` owns aggregation, the CLI only renders and sets exit code.

**Quick validation**
```bash
pytest tests/doctor -q && pytest tests/cli/test_commands.py -q -k doctor
```

### 30. Proposal metadata index + doctor drift visibility

**Core behavior**
- Proposal lifecycle metadata is tracked in a dedicated index alongside proposal markdown files so review state survives beyond filename inspection.
- The metadata index records proposal status as one of `pending`, `applied`, or `rejected`.
- `skill_manage` updates lifecycle metadata when proposals are applied or rejected instead of leaving proposal state implicit.
- `nanobot doctor` surfaces proposal health and drift so operators can see mismatches between proposal files and the metadata index.

**Contract details**
- Proposal markdown remains the review artifact under `workspace/memory/skill-proposals/`.
- Proposal metadata lives in the branch-local index implemented by `nanobot/agent/skill_proposal_metadata.py` and consumed by `nanobot/agent/skill_proposals.py`.
- `pending` means the proposal file exists and is still actionable.
- `applied` means the proposal was promoted into a workspace skill and should no longer appear as pending work.
- `rejected` means the proposal was explicitly declined and should remain visible as historical review state rather than silently disappearing from the index.
- Doctor drift includes cases where proposal files exist without matching metadata, metadata references missing proposal files, or lifecycle state no longer matches on-disk reality.

**Files to protect during future merges**
- `nanobot/agent/skill_proposal_metadata.py`
- `nanobot/agent/skill_proposals.py`
- `nanobot/agent/tools/skill_manage.py`
- `nanobot/doctor/checks/skills.py`
- `tests/agent/test_skill_proposal_metadata.py`
- `tests/agent/test_skill_proposals.py`
- `tests/tools/test_skill_manage_tool.py`
- `tests/doctor/test_skill_checks.py`

**Resolution priority**
1. Keep proposal state explicit in the metadata index; do not regress to inferring lifecycle solely from which markdown files happen to exist.
2. Keep the lifecycle vocabulary limited to `pending`, `applied`, and `rejected` unless a real migration updates both runtime code and this contract.
3. Keep `skill_manage` as the state transition point for apply/reject flows so metadata and proposal files cannot drift under normal usage.
4. Keep doctor reporting proposal health/drift against both the proposal directory and the metadata index so merge regressions are operator-visible.

**Quick validation**
```bash
python3 -m pytest tests/agent/test_skill_proposal_metadata.py tests/agent/test_skill_proposals.py tests/tools/test_skill_manage_tool.py tests/doctor/test_skill_checks.py -q
```

### 31. OpenAI-compatible image generation tool

**Core behavior**
- `tools.imageGeneration.enabled` gates a built-in `generate_image` tool for chat-channel users.
- Supported providers are `openai` and `custom`; custom uses `providers.custom.apiKey` / `providers.custom.apiBase` for OpenAI-compatible image generation APIs.
- `ImageGenerationService` calls OpenAI image generation, saves the image under workspace-aware `media/generated/`, and returns compact metadata only.
- `generate_image` auto-sends the generated file to the current chat via `OutboundMessage(media=[path])`.
- Tool results are intentionally compact: no base64, local file path, provider JSON, or raw exception detail is returned to the model.
- Registration is gateway-only by default: the gateway opts in with `enable_image_generation_tool=True` because it rewires delivery through `_deliver_to_channel`; CLI/API/programmatic paths do not expose the tool unless a real media delivery path is explicitly provided.

**Files to protect during conflicts**
- `nanobot/config/schema.py` → `ImageGenerationToolConfig`, `ToolsConfig.image_generation`
- `nanobot/image_generation.py` → OpenAI image generation service and file persistence
- `nanobot/agent/tools/image_generation.py` → `GenerateImageTool`, compact/sanitized model-visible results
- `nanobot/agent/loop.py` → opt-in registration and context propagation for `generate_image`
- `nanobot/cli/commands.py` → gateway opt-in and `_deliver_to_channel` callback wiring
- `docs/configuration.md` → user-facing config example

**Resolution priority**
1. Keep `tools.imageGeneration.enabled = false` by default.
2. Keep registration conditional on explicit runtime opt-in, enabled config, and OpenAI API key; do not expose the tool in runtimes that cannot deliver media.
3. Keep success and failure tool results compact and sanitized.
4. Keep generated image bytes out of model-visible tool results and session text.
5. Keep `gpt-image-1` requests from sending unsupported `response_format`; only DALL-E models request `b64_json` explicitly.
6. Keep `custom` routed through `Config.get_image_generation_provider()` so image generation can use a different OpenAI-compatible provider from the primary chat model.

**Config example**
```json
{
  "providers": {
    "openai": {
      "apiKey": "${OPENAI_API_KEY}"
    }
  },
  "tools": {
    "imageGeneration": {
      "enabled": true,
      "provider": "openai",
      "model": "gpt-image-1",
      "size": "1024x1024",
      "quality": "auto"
    }
  }
}
```

**Quick validation**
```bash
python3 -m pytest tests/test_image_generation_config.py tests/test_image_generation_service.py tests/tools/test_image_generation_tool.py tests/test_image_generation_runtime_wiring.py tests/agent/test_loop_tool_context.py -q
```

### 32. Constrained scripted workflows

**Core behavior**
- Workspace-local workflows live under `workspace/workflows/<name>.md`.
- Workflow files use YAML frontmatter with matching `name` and non-empty `description`.
- Workflow steps are parsed from numbered markdown list items.
- The runner is instruction-only: it never executes commands, mutates files, invokes tools, branches, loops, or expands templates.
- Workflows are exposed through read-only agent tools `workflow_list` and `workflow_run`.
- Workflows are also exposed through `/workflow list`, `/workflow show <name>`, `/workflow run <name>`, `/workflow step <name>`, `/workflow next`, and `/workflow abort`.
- Step-by-step mode tracks session-local progress and fails closed if the workflow file changes during an active run.

**Files to protect during future merges**
- `nanobot/workflows/types.py`
- `nanobot/workflows/store.py`
- `nanobot/workflows/progress.py`
- `nanobot/agent/tools/workflow.py`
- `nanobot/agent/loop.py`
- `nanobot/command/builtin.py`
- `tests/workflows/test_store.py`
- `tests/workflows/test_progress.py`
- `tests/tools/test_workflow_tool.py`
- `tests/command/test_builtin_workflow.py`

**Resolution priority**
1. Keep workflows workspace-local under `workflows/`; do not add bundled or remote workflows in v1.
2. Keep the runner instruction-only; workflow content must never be executed by the workflow subsystem.
3. Keep numbered markdown list items as the v1 step format.
4. Keep both surfaces: agent tools for discovery/use by the model and slash commands for explicit user control.
5. Keep file-change mismatch in step mode fail-closed with a restart message.

**Quick validation**
```bash
python3 -m pytest tests/workflows tests/tools/test_workflow_tool.py tests/command/test_builtin_workflow.py tests/command/test_router_dispatchable.py -q
```

### 32. Sub-Agent Architecture

**Core behavior**
- Main agent (deepseek-v4) delegates recall and curation workloads to configurable sub-agents running on cheap models
- Sub-agents are defined via markdown files in `agents/<name>.md` with YAML frontmatter (same pattern as skills)
- A single `delegate` tool on the main agent replaces multiple specialized tool schemas
- Each sub-agent has an isolated tool set, model, temperature, max iterations, and **per-agent fallback model chain**
- Workspace agents override built-in agents with the same name; config overrides frontmatter
- **Runtime agent creation**: agents written to `agents/<name>.md` at runtime are discovered instantly — no restart needed
- **Channel override independence**: sub-agents use their own configured model, not the channel override model

**Token saving**
- `session_search` tool schema (~500 tokens) removed from main agent's system prompt
- Recall results are distilled summaries (~200 chars) vs raw excerpts (~600 chars)
- Curator runs on cheap model, offline — zero main agent token impact
- Memory context fencing prevents the model from confusing recalled memory with new instructions
- Trivial-prompt skip (≤3 tokens) avoids injecting memory on meaningless turns ("ok", "yes", "/status")
- Context-length auto-compact triggers at 75% of model context window (matching opencode CLI behavior)

**Token usage tracking**
- Sub-agent token usage (prompt_tokens, completion_tokens, cached_tokens) is accumulated and merged into main agent's `_last_usage`
- DeepSeek's `prompt_cache_hit_tokens` is normalized to `cached_tokens` and included in `/status` cache percentage display
- `DelegateTool.cumulative_usage` aggregates across all sub-agent calls, reset each turn via the main loop

**Built-in agents**
- `nanobot/agents/recall.md` — session search + summarization, model: `deepseek-v4-flash` (trigger: on_demand)
- `nanobot/agents/curator.md` — skill lifecycle + umbrella-building, model: `kimi-k2.5` (trigger: idle)

**Per-sub-agent fallback models**
- `fallback_models` supported in both agent `.md` frontmatter and config overrides (config wins if both set)
- Config override schema (`SubAgentConfig`): `model`, `temperature`, `tools`, `fallbackModels`, `provider`
- If not configured, sub-agent inherits main agent's `fallbackModels` list
- Recommended: set sub-agent fallbacks to cheap/medium models to avoid escalating to premium unnecessarily

**Agent file format**
```yaml
---
name: stock-analyst
description: Analyzes stock market data and trends
model: deepseek-v4-flash
temperature: 0.1
fallback_models:
  - minimax-m2.7
  - glm-5.1
tools:
  - read_file
  - shell
max_iterations: 5
max_tokens: 4000
trigger: on_demand
---
You are a stock market analysis agent.
```

**Config example**
```jsonc
{
  "subagents": {
    "recall": {
      "model": "deepseek-v4-flash",
      "fallbackModels": ["deepseek-v3.2", "minimax-m2.7"]
    },
    "curator": {
      "model": "kimi-k2.5",
      "fallbackModels": ["glm-5.1"]
    }
  }
}
```

**Files to protect**
- `nanobot/agent/subagents.py` — AgentConfig dataclass (with `fallback_models`), AgentLoader for YAML-frontmatter .md agent files
- `nanobot/agent/tools/delegate.py` — DelegateTool dispatches LLM tasks to sub-agents with fallback chain + cumulative usage tracking
- `nanobot/agents/` — built-in agent definitions
- `nanobot/agent/loop.py` — delegate registration, tool factory map, curator wiring, sub-agent usage merge into `_last_usage`
- `nanobot/config/schema.py` — SubAgentConfig (with `fallbackModels`, `provider`), SubAgentsConfig, CuratorConfig

**Quick validation**
```bash
python3 -m pytest tests/agent/test_subagents.py tests/tools/test_delegate.py -q
```

### 33. SQLite + FTS5 Session Store

**Core behavior**
- Replaces JSONL file scan with SQLite-backed FTS5 for full-text session search
- WAL mode for concurrent reads; `check_same_thread=False` for async channel safety
- BM25 relevance ranking via FTS5 `ORDER BY rank`
- Sessions table with metadata (id, source, model, title, started_at, token_count, parent_session_id)
- Messages table with FTS5 virtual table for content search
- One-time migration: existing JSONL sessions imported on first boot; JSONL kept as backup
- SessionManager writes to both JSONL (canonical) and SQLite (write-through, best-effort)

**Files to protect**
- `nanobot/session/store.py` — SessionStore class
- `nanobot/session/manager.py` — SessionManager integration
- `nanobot/session/search.py` — kept for compatibility, replaced by store.py
- `nanobot/agent/tools/session_search.py` — rewritten for FTS5 store, three modes (recent browse, keyword search)

**Quick validation**
```bash
python3 -m pytest tests/session/test_store.py tests/session/test_store_integration.py tests/tools/test_session_search_tool.py -q
```

### 34. Autonomous Curator

**Core behavior**
- Idle-triggered (default 7-day interval) skill library maintenance
- Phase 1 (pure logic, zero LLM tokens): auto-transitions active→stale(30d)→archived(90d); reactivates stale if recently used
- Phase 2 (cheap-model LLM pass): umbrella-building consolidation — merges narrow sibling skills into class-level umbrellas, demotes session-specific content to references/templates/scripts
- Safety guardrails: only touches agent-created skills, never deletes (archive only), never touches pinned skills
- Per-run reports with structured YAML output (consolidations + prunings lists)
- Configurable via `curator.*` config keys

**Skill lifecycle states**
- `active` — in use (default)
- `stale` — unused > 30 days (auto; reverts to active if used)
- `archived` — unused > 90 days (moved to `skills/.archive/`, recoverable)
- `pinned` — opt-out from all auto-transitions

**Skill usage telemetry**
- `.skill_usage.json` sidecar tracking: use_count, patch_count, view_count, last_used_at, last_patched_at, last_viewed_at, state, pinned
- Atomic writes via tempfile + os.replace
- Bumped on: skill invocation, skill_manage patch, skill_view

**Files to protect**
- `nanobot/agent/curator.py` — CuratorScheduler with idle detection, lifecycle logic, umbrella-building
- `nanobot/agent/skill_usage.py` — SkillUsageStore with atomic writes
- `nanobot/agents/curator.md` — built-in curator agent definition
- `nanobot/agent/loop.py` — curator initialization and idle check in main loop

**Quick validation**
```bash
python3 -m pytest tests/agent/test_skill_usage.py -q
```

### 35. Token & Performance Optimizations

**Memory context fencing** — MEMORY.md/USER.md injection wrapped in `<memory-context>` tags with explicit system note ("NOT new user input"). Prevents model confusion. +50 tokens.

**Context-length auto-compact** — Compaction triggers when prompt tokens exceed 75% of model context window (matching opencode CLI behavior). Keeps existing time-based trigger as fallback.

**Trivial-prompt skip** — Skips memory injection for user messages ≤3 tokens (e.g., "ok", "yes", "/status"). Saves ~200-500 tokens on meaningless turns.

**Files to protect**
- `nanobot/agent/context.py` — memory fencing, trivial-prompt skip
- `nanobot/agent/memory.py` — Consolidator 75% threshold check

**Quick validation**
```bash
python3 -m pytest tests/agent/test_consolidator.py tests/agent/test_context.py -q
```
