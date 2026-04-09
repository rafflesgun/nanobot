---
name: preserve-local-features-merge
description: Use when merging upstream changes into this nanobot-rg workspace and local branch-specific behavior must survive conflict resolution, targeted feature checks, and full test verification.
---

# Preserve Local Features During Upstream Merge

## Overview
Use this skill when merging `origin/main` into the local nanobot branch while preserving branch-specific behavior documented in `docs/features/raffles-local-features-2026.md`.

Core rule: a merge is not complete when conflicts are gone. A merge is complete only when the documented local features still hold and verification is green.

## When to Use
- Merging `origin/main` or upstream main into this repo
- Resolving conflicts in `nanobot/channels/telegram.py`, `nanobot/agent/loop.py`, `nanobot/agent/subagent.py`, `nanobot/command/builtin.py`, `nanobot/config/schema.py`, or related tests
- Any time upstream changes may break Telegram topics, per-topic overrides, cron topic delivery, subagents, fallback models, TTS, or local command behavior

Do not use for routine feature work unrelated to upstream merge preservation.

## Required Inputs
- Upstream branch, usually `origin/main`
- Local feature contract: `docs/features/raffles-local-features-2026.md`

## Workflow
1. Inspect repo state first.
2. Read the local feature contract before making conflict decisions.
3. Merge upstream.
4. Identify conflicted files and map them to protected local features.
5. Resolve conflicts with local behavior preservation as the priority unless the user explicitly wants a behavior changed.
6. Run targeted tests for touched protected features.
7. Run the full test suite.
8. Update the feature contract if behavior changed intentionally or the contract became stale.
9. Only then report completion or create a commit.

## Protected Local Features
- Telegram topic-scoped session keys and topic-aware routing
- Topic-scoped `/model`, `/model temp`, `/tts`, `/stats`, and builtin command behavior
- Topic `thread_id` visibility in runtime context
- Cron job creation and delivery with `thread_id`
- Configured subagents via `spawn(subagent_id)`
- Parent session model override propagation into spawned subagents
- Ordered fallback models, including bare `429` fallback eligibility
- TTS reliability and persistence across restart
- Mention-only Telegram group handling
- Random ACK reaction emoji and typing/thinking behavior

## High-Risk Files
- `nanobot/channels/telegram.py`
- `nanobot/agent/loop.py`
- `nanobot/agent/context.py`
- `nanobot/agent/subagent.py`
- `nanobot/agent/tools/spawn.py`
- `nanobot/agent/tools/message.py`
- `nanobot/agent/tools/cron.py`
- `nanobot/command/builtin.py`
- `nanobot/config/schema.py`
- `nanobot/config/paths.py`
- `tests/test_telegram_builtin_commands_topic.py`
- `tests/test_cron_topic_delivery.py`
- `tests/agent/test_fallback_models.py`
- `tests/agent/test_configured_subagents.py`
- `tests/test_tts.py`

## Verification Checklist
- `pytest tests/test_cron_topic_delivery.py -q`
- `pytest tests/test_telegram_builtin_commands_topic.py -q`
- `pytest tests/agent/test_fallback_models.py -q`
- `pytest tests/agent/test_configured_subagents.py -q`
- `pytest tests/test_tts.py -q`
- `pytest tests/agent/test_context_prompt_cache.py -q`
- `pytest -q`

If a protected feature changed, run its targeted validation from the feature contract even if the conflict looked unrelated.

## Merge Decision Rules
- Prefer the version that keeps `message_thread_id` flowing through metadata, session keys, runtime context, and outbound replies.
- Preserve topic-scoped keys like `telegram:{chat_id}:topic:{thread_id}`.
- Preserve persistence for model, temperature, and TTS overrides across restart.
- Preserve fallback ordering and error eligibility unless the user explicitly changes the policy.
- Preserve subagent topic routing and model override propagation.
- Do not drop local tests just because upstream did not have them.

## Completion Standard
Do not say the merge is done unless:
- conflicts are resolved
- protected behaviors were checked against the contract
- targeted tests pass
- full `pytest -q` passes, or remaining skips are expected optional-environment skips

## Final Report Template
- Upstream branch merged
- Conflicted files resolved
- Protected features checked
- Targeted tests run
- Full test result
- Contract doc updated or confirmed current
- Remaining risks, if any
