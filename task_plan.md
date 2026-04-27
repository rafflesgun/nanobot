# Merge Origin Main Into Local Features

## Goal
Merge `origin/main` into `raffles/local-features` while preserving the local feature contract in `docs/features/raffles-local-features-2026.md`.

## Phases

| Phase | Status | Notes |
|---|---|---|
| Inspect repo and contract | complete | Working tree was clean before merge; contract read. |
| Fetch and merge upstream | complete | `git fetch origin main`; `git merge origin/main` produced conflicts. |
| Resolve conflicts | complete | Removed conflict markers; `git diff --check` and `python3 -m py_compile` passed after fixing one missing comma in cron delivery. |
| Run targeted tests | complete | Required protected-feature test checklist passed. |
| Run full suite | complete | `pytest -q`: 2655 passed, 5 skipped. |
| Contract check | complete | Updated merge-history line for 27 April 2026; no protected behavior intentionally changed. |
| Final report | pending | Include conflicts, protected features, tests, risks. |

## Conflicted Files

- `nanobot/agent/context.py`
- `nanobot/agent/loop.py`
- `nanobot/agent/memory.py`
- `nanobot/agent/runner.py`
- `nanobot/agent/tools/cron.py`
- `nanobot/agent/tools/message.py`
- `nanobot/agent/tools/shell.py`
- `nanobot/bus/events.py`
- `nanobot/channels/slack.py`
- `nanobot/channels/telegram.py`
- `nanobot/cli/commands.py`
- `nanobot/command/builtin.py`
- `nanobot/cron/service.py`
- `nanobot/cron/types.py`
- `nanobot/nanobot.py`
- `nanobot/providers/openai_compat_provider.py`
- `tests/agent/test_dream.py`
- `webui/src/hooks/useNanobotStream.ts`

## Decision Rules

- Preserve local topic-scoped Telegram session behavior and outbound `message_thread_id` propagation.
- Preserve cron `thread_id` creation and delivery.
- Preserve local fallback model eligibility and ordering.
- Preserve configured subagent behavior and model override propagation.
- Preserve TTS reliability and persisted overrides.
- Prefer minimal conflict resolutions that retain both local and upstream changes.

## Errors Encountered

| Error | Attempt | Resolution |
|---|---|---|
| Merge conflicts from `git merge origin/main` | 1 | Resolving manually with local feature contract as priority. |
| `python` command not found | 1 | Re-ran syntax check with `python3`. |
| SyntaxError in `nanobot/cli/commands.py` missing comma after `OutboundMessage(...)` | 1 | Added comma and reran `python3 -m py_compile` successfully. |
