# Task Plan: Implement selected upstream PRs and WebUI integration plan

## Goal
Create and execute a phased implementation plan for the selected upstream PRs that are still valuable for `raffles/local`, with each implementation phase ending in a git commit only after its focused tests pass.

## Current Phase
Phase 7

## Phases

### Phase 1: Requirements & Cross-Check
- [x] Review the requested PR list
- [x] Cross-check each PR against the previous analysis and current local branch
- [x] Identify which PRs are already implemented, overlapping, or still valuable
- [x] Document findings in findings.md
- **Status:** complete

### Phase 2: Draft rollout plan and commit policy
- [x] Define implementation order based on impact, merge risk, and overlap with local changes
- [x] Define per-phase test gates
- [x] Define per-phase git commit requirement after tests pass
- [x] Separate core repo work from WebUI packaging/integration work
- **Status:** complete

### Phase 3: Reliability fixes batch
- [x] Implement PR #2449 cron reminder notification fix
- [x] Implement PR #2430 stateless heartbeat by default, reconciled with local DM-only heartbeat behavior
- [x] Run focused tests for cron, evaluator, heartbeat, and gateway flows
- [x] Commit Phase 3 after all targeted tests pass
- **Status:** complete

### Phase 4: Fallback model enhancement
- [x] Implement PR #2417 ordered fallback models
- [x] Preserve backward compatibility with existing local `fallback_model`
- [x] Add migration and runtime tests for both single and ordered fallback config
- [x] Commit Phase 4 after all targeted tests pass
- **Status:** complete

### Phase 5: Configured subagents
- [x] Implement PR #2368 configured subagents
- [x] Keep scope limited to configured subagents, not full peer-agent architecture
- [x] Reconcile with local spawn, message bus, and channel manager behavior
- [x] Commit Phase 5 after all targeted tests pass
- **Status:** complete

### Phase 6: Optional low-risk additions
- [x] Add PR #2451 `ipinfo` skill if still desired
- [x] Run focused skill/discovery sanity checks
- [x] Commit Phase 6 after tests pass
- **Status:** complete

### Phase 7: WebUI single-image planning
- [ ] Assess `nanobot-webui` integration points and packaging constraints
- [ ] Decide whether to vendor, submodule, or produce a composed Docker build
- [ ] Draft a separate implementation plan for single-image delivery
- **Status:** in_progress

### Phase 8: Delivery
- [ ] Keep planning files and local feature ledger updated as phases land
- [ ] Summarize completed work, tests, commits, and remaining risks
- **Status:** pending

## Key Questions
1. How should PR #2430 be merged with existing local heartbeat history-bounding and DM-only routing without regressing intended local behavior?
2. Should PR #2417 support both `fallback_model` and `fallback_models`, or should one be normalized into the other during config load?
3. Should configured subagents in PR #2368 be implemented without adopting the broader multi-agent design from PR #2064?
4. Is `nanobot-webui` intended as a packaging-only addition, or should core repo commands and Docker assets be extended directly?

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Skip PRs #2457, #2436, #2435, #2408, and #2397 | Equivalent behavior is already present locally, so re-implementing them would waste effort and risk regressions |
| Implement in order `2449 -> 2430 -> 2417 -> 2368 -> 2451` | This maximizes reliability and usefulness first, then controlled extensibility |
| Treat `nanobot-webui` as a separate workstream | It is packaging/integration work, not a small upstream repo patch |
| Require a git commit only after each phase's targeted tests pass | Matches user instruction and keeps history clean and defensible |
| Defer PR #2064 | It overlaps configured-subagent work but is much broader and riskier |
| Keep `fallback_model` as the first compatibility fallback, then append `fallback_models` | Preserves existing configs while enabling ordered fallback chains without a breaking migration |
| Keep configured subagents as `agents.defaults` overlays selected only through `spawn(subagent_id)` | Delivers the useful backend specialization from PR #2368 without adopting a larger multi-agent architecture |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| Missing `asyncio` import in new CLI regression test | 1 | Fixed by adding the import; focused Phase 3 test gate passed on rerun |

## Notes
- Phase commits should be scoped and non-interactive.
- Do not combine multiple major architectural changes into one commit.
- Update `docs/features/raffles-local-features-2026.md` after each landed behavior change that is branch-specific.
