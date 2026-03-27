# Findings & Decisions

## Requirements
- Review the newly requested PR list and cross-check it with the previous upstream PR analysis.
- Draft an implementation plan, not code, for the selected work.
- Organize the work into phases.
- For each implementation phase, require tests to pass before creating a git commit.
- Include the separate request to add WebUI into a single Docker image as part of planning, but not necessarily in the same code phase as core repo PRs.

## Research Findings
- PR #2457 is already effectively implemented locally: cron job executions already use timestamped session keys in `nanobot/cli/commands.py`.
- PR #2436 is already effectively implemented locally: memory consolidation already has `asyncio.wait_for(timeout=120.0)` and RAW archive fallback in `nanobot/agent/memory.py`.
- PR #2435 is already effectively implemented locally: heartbeat already skips the LLM call when no actionable tasks are found in `HEARTBEAT.md`.
- PR #2408 is already effectively implemented locally: `read_file` already uses line-by-line streaming with bounded output.
- PR #2397 is already effectively implemented locally: `cron` already has a `name` parameter, and the local `cron` skill already uses the playbook/task-package pattern.
- PR #2449 remains useful: it improves cron reminder notification evaluation and appears not to be present locally.
- PR #2430 remains useful: it goes beyond current local heartbeat hardening by making heartbeat stateless by default and adding concurrency protection.
- PR #2417 remains useful: local branch has single `fallback_model`, while this PR extends the concept to ordered fallbacks.
- PR #2368 remains useful: current schema still has only `agents.defaults`, so configured subagents are not yet present.
- PR #2064 overlaps the earlier multi-agent recommendations but is broader than needed for first adoption.
- `nanobot-webui` is a separate repository with FastAPI + React packaging and its own Docker story; single-image integration should be treated as a packaging/ops track rather than a small upstream PR.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Reliability PRs come before architecture PRs | Lower merge risk and immediate user value |
| Use PR #2368 as the first multi-agent-related step | It is narrower and safer than PR #2064 |
| Keep WebUI planning separate from core PR implementation phases | It has different code ownership, build, and release concerns |
| Preserve existing local behavior where stronger than upstream | The branch already contains custom Telegram, heartbeat, fallback, and security work that should not be regressed |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Several requested PRs were already present in equivalent form locally | Filtered them out of the implementation queue and documented them as complete |

## Resources
- Local feature ledger: `docs/features/raffles-local-features-2026.md`
- Requested PR metadata cached in `/tmp/pr-*.json`
- Requested PR changed-file metadata cached in `/tmp/pr-*-files.json`
- WebUI README: `https://raw.githubusercontent.com/rafflesgun/nanobot-webui/main/README.md`

## Visual/Browser Findings
- No image/PDF-specific findings captured in this planning pass.

---
*Update this file after every 2 view/browser/search operations*
*This prevents visual information from being lost*
