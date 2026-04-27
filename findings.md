# Merge Findings

## Initial State

- Current branch: `raffles/local-features` tracking `origin/raffles/local-features`.
- Working tree was clean before merge.
- `origin/main` advanced from `3441d5f` to `d89a824` before merge.

## Local Feature Contract Highlights

- Telegram topic sessions use `telegram:{chat_id}:topic:{thread_id}` and preserve `message_thread_id` through metadata, runtime context, commands, cron, and subagent messages.
- Fallback models are ordered and include broad provider-error eligibility including bare `429` and temporarily-unavailable messages.
- Subagents support configured profiles and inherit parent model overrides unless explicitly set.
- TTS sends text before voice generation, uses timeout protection, and persists overrides.
- Workspace restrictions use nested `restrictToWorkspace` with `enabled`, `extraRead`, and `extraWrite`.

## Conflict Inventory

- Protected/high-risk conflicts include `agent/context.py`, `agent/loop.py`, `agent/tools/cron.py`, `agent/tools/message.py`, `agent/tools/shell.py`, `channels/telegram.py`, `cli/commands.py`, `command/builtin.py`, `cron/service.py`, `cron/types.py`, and `providers/openai_compat_provider.py`.
- Additional conflicts include `memory.py`, `runner.py`, `bus/events.py`, `slack.py`, `nanobot.py`, `tests/agent/test_dream.py`, and `webui/src/hooks/useNanobotStream.ts`.

## Resolution Notes

- `agent/loop.py`: kept local model/temperature overrides, ordered fallback models, topic runtime context, incremental save callbacks, and subagent topic routing; merged upstream ask-user, timestamped history, metadata routing, and pending-message document extraction.
- `cron/types.py`, `cron/service.py`, `agent/tools/cron.py`: kept local `thread_id` and merged upstream `channel_meta` / `session_key` persistence.
- `agent/tools/message.py`, `bus/events.py`, `channels/slack.py`, `channels/telegram.py`: kept local topic metadata propagation and merged upstream buttons/inline keyboard support.
- `channels/telegram.py`: restored text-before-TTS ordering per local TTS reliability contract while keeping upstream media/video/button additions and RetryAfter handling.
- `providers/openai_compat_provider.py`: kept `max_retries=0`, explicit timeout, and merged upstream local-endpoint HTTP client and provider-spec thinking map.
- `agent/memory.py`, `agent/runner.py`, `tests/agent/test_dream.py`: kept local learning loop behaviors and merged upstream prompt caps / ask-user interruption behavior.
