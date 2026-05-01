# Design: Sub-Agent Architecture with Long Memory & Self-Evolution

**Date:** 2026-05-01
**Status:** draft
**Branch:** `raffles/local-features`

## Summary

Delegate session recall and skill-curation workloads to configurable, purpose-built sub-agents running on cheap models. The main agent (deepseek-v4) keeps a lean tool set and system prompt. Sub-agents have isolated model/tool/temperature profiles defined via markdown files in `agents/`. Token savings come from removing heavy tool schemas (session_search, skill_manage) from the main agent's system prompt and running batch workloads (curator) on cheap models off the main context.

---

## 1. Sub-Agent Architecture

### 1.1 Architecture overview

```
+-----------------------------------------------+
|  Main Agent (deepseek-v4)                     |
|  Tools: file ops, shell, memory, skill_view,  |
|         workflow, MCP, delegate               |
|  ~60% of current system prompt tokens         |
|                                                |
|  +--------------+   +------------------+       |
|  | Recall Agent |   |  Curator Agent   |       |
|  | gpt-4o-mini  |   |  gpt-4o-mini     |       |
|  | session_     |   |  skill_manage    |       |
|  | search only  |   |  read/write/edit |       |
|  | temp=0.1     |   |  temp=0.2        |       |
|  | on-demand    |   |  idle-triggered  |       |
|  +------+-------+   +-------+----------+       |
|         | distilled         | auto-executes    |
|         | summary           | consolidations   |
|         v                   v                  |
|  +----------------------------------------+    |
|  |        Shared Infrastructure           |    |
|  |  FTS5 SQLite  |  MemoryStore  |  Git   |    |
|  +----------------------------------------+    |
+-----------------------------------------------+
```

### 1.2 Agent file format (`agents/<name>.md`)

Same pattern as `skills/<name>/SKILL.md`: markdown body with YAML frontmatter.

```markdown
---
name: code-reviewer
description: Reviews code changes for bugs, style, and security issues
model: openai/gpt-4o-mini
temperature: 0.1
tools:
  - read_file
  - shell
max_iterations: 5
max_tokens: 4000
trigger: on_demand
---

You are a code review agent. When given a task:

1. Read the relevant files using read_file
2. Analyze for: bugs, style violations, security issues, performance problems
3. Return a structured review with severity levels
4. Include specific line references and suggested fixes
```

#### Frontmatter fields

| Field | Required | Default | Description |
|---|---|---|---|
| `name` | yes | (filename) | Agent identifier, used in `delegate(agent="name")` |
| `description` | yes | — | Shown in agent list; helps main agent decide when to delegate |
| `model` | no | main agent's model | Which model this sub-agent uses |
| `temperature` | no | 0.0 | Sampling temperature |
| `tools` | no | `[]` | Explicit allowlist. Only these tools are loaded. |
| `max_iterations` | no | 3 | Max tool-calling iterations |
| `max_tokens` | no | 4096 | Response token cap |
| `trigger` | no | `on_demand` | `on_demand` (main agent calls delegate), `idle` (runs in background), `boot` (runs at session start) |
| `channel` | no | all | Limit to specific channels (e.g., `telegram`, `cli`) |

#### Precedence

1. Workspace `agents/<name>.md` overrides built-in `nanobot/agents/<name>.md`
2. Config `subagents.<name>.model` / `.tools` overrides frontmatter (per-deployment tuning without editing agent files)

### 1.3 Built-in agents

```
nanobot/agents/
  recall.md       — session search + summarization (trigger: on_demand)
  curator.md      — skill lifecycle + umbrella-building (trigger: idle)
```

Users can override in `agents/recall.md` or `agents/curator.md`.

### 1.4 Delegation tool

A single `delegate` tool on the main agent:

```json
{
  "name": "delegate",
  "description": "Delegate a task to a specialized sub-agent — recall, curator, or custom agents in agents/",
  "parameters": {
    "agent": {
      "type": "string",
      "description": "Sub-agent name to delegate to"
    },
    "task": {
      "type": "string",
      "description": "Natural language task for the sub-agent"
    }
  },
  "required": ["agent", "task"]
}
```

**Token saving:** One ~300-token schema replaces N specialized schemas (session_search, etc.). As new sub-agents are added, the delegate tool description gets updated with available agent names — no schema growth.

---

## 2. Session Recall (Recall Agent)

### 2.1 Storage: SQLite with FTS5

Replace JSONL file scan with SQLite-backed FTS5. WAL mode for concurrent reads.

```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    model TEXT,
    title TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    message_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0,
    parent_session_id TEXT,
    FOREIGN KEY (parent_session_id) REFERENCES sessions(id)
);

CREATE VIRTUAL TABLE messages_fts USING fts5(
    session_id, role, content,
    tokenize='porter unicode61'
);
```

Migration: existing JSONL sessions imported on first boot. JSONL kept as read-only backup.

### 2.2 Recall agent (built-in `recall.md`)

- **Tool:** `session_search` (the only tool)
- **Model:** `openai/gpt-4o-mini` (configurable per frontmatter or config)
- **Trigger:** `on_demand` — main agent calls `delegate(agent="recall", task="search past conversations about X")`

#### Three modes

1. **Recent browse** (query empty) — returns last N session titles/timestamps. Zero LLM tokens.
2. **Keyword search** (query provided) — FTS5 relevance-ranked → load top-N sessions → parallel LLM summaries via cheap model → return distilled results
3. **Recap** — returns summary of all sessions since last recap call

#### Search → summarize pipeline

```
1. FTS5 search finds matching messages ranked by BM25 relevance
2. Groups by session, deduplicates (resolves child sessions to root parent)
3. Excludes current session lineage
4. Loads top-N session transcripts, truncates around match positions
5. Parallel LLM summarization (bounded concurrency, configurable 1-5)
6. Returns per-session summaries with metadata (session_id, date, source, model)
7. Fallback: if summarizer fails, returns raw preview (never silent drop)
```

#### Session lineage

Walk `parent_session_id` chains to the root parent. Compression and delegation create child sessions — both belong to the same active conversation and should be deduplicated in search results.

### 2.3 Token impact

| Item | Before | After |
|------|--------|-------|
| `session_search` schema in main prompt | ~500 tokens/turn | **0** (schema in recall agent only) |
| Recall result in context | 600 chars raw excerpt | ~200 chars distilled summary |
| Search quality | term count (grep) | FTS5 BM25 relevance ranking |

---

## 3. Autonomous Curator (Curator Agent)

### 3.1 Lifecycle model

Skills have four states (stored in `.skill_usage.json`):

| State | Meaning | Transition |
|-------|---------|------------|
| `active` | In use | Default for new skills |
| `stale` | Unused > 30d | Auto from active; reverts to active if used again |
| `archived` | Unused > 90d | Moved to `skills/.archive/`. Recoverable. |
| `pinned` | Opt-out | Bypasses all auto-transitions |

### 3.2 Curator agent (built-in `curator.md`)

- **Tools:** `skill_manage` (patch/archive/create), `read_file`, `write_file`, `shell`
- **Model:** `openai/gpt-4o-mini` (configurable)
- **Trigger:** `idle` — runs when agent is idle AND `idle_interval_hours` (default 168 = 7 days) has elapsed
- **Execution:** **Auto-executes** — no human review gate for consolidations or archiving

### 3.3 Two-phase execution

**Phase 1 — Pure logic (zero LLM tokens):**

```
apply_automatic_transitions():
  for each agent-created skill:
    if pinned → skip
    if last_activity > archive_after_days (90d) → archive
    elif last_activity > stale_after_days (30d) → mark stale
    elif state=stale AND recent activity → reactivate
```

**Phase 2 — LLM umbrella-building pass (cheap model, batch):**

```
1. Scan all agent-created skills for prefix clusters
2. For each cluster with 2+ members, decide:
   a. MERGE INTO EXISTING UMBRELLA — patch umbrella, archive siblings
   b. CREATE NEW UMBRELLA — write class-level SKILL.md, archive siblings
   c. DEMOTE TO SUPPORT FILES — move content to references/templates/scripts, archive sibling
3. Write per-run report to logs/curator/{timestamp}/ (run.json + REPORT.md)
4. Output structured YAML: consolidations list + prunings list
```

### 3.4 Safety guardrails

- Only touches agent-created skills (never built-in or hub-installed)
- Never deletes — only archives (recoverable)
- Never touches pinned skills
- Configurable via `curator.*` config keys: `enabled`, `interval_hours`, `stale_after_days`, `archive_after_days`

### 3.5 Skill usage telemetry

`.skill_usage.json` sidecar (same directory as skills, same atomic-write pattern as `.metadata.json`):

```json
{
  "my-skill": {
    "created_at": "2026-04-01T10:00:00Z",
    "state": "active",
    "pinned": false,
    "use_count": 12,
    "view_count": 5,
    "patch_count": 2,
    "last_used_at": "2026-04-28T14:00:00Z",
    "last_viewed_at": "2026-04-28T14:00:00Z",
    "last_patched_at": "2026-04-15T09:00:00Z"
  }
}
```

Bumped on: skill invocation (`use_count`), skill_manage patch (`patch_count`), skill_view (`view_count`). All bumps are best-effort — a broken sidecar never breaks the underlying tool call.

### 3.6 Token impact

| Item | Before | After |
|------|--------|-------|
| Curator LLM calls | N/A (didn't exist) | Runs on cheap model, idle-triggered, **zero main token impact** |
| Skill sprawl | Unbounded accumulation | Auto-archived at 90d, consolidated by umbrella-building |
| Lifecycle visibility | None | `nanobot doctor` can report stale/archived/pinned skills |

---

## 4. Token & Performance Optimizations

### 4.1 Memory context fencing

Wrap MEMORY.md/USER.md injection in explicit tags:

```
<memory-context>
[System note: The following is recalled memory, NOT new user input.]
...memory content...
</memory-context>
```

**Cost:** +50 tokens. **Benefit:** Prevents model from treating old memory as new instructions.

### 4.2 Context-length-based auto-compact (75% threshold)

Fire compaction when context reaches 75% of the model's context window — matching opencode CLI behavior. Keeps existing time-based trigger as fallback; length-based becomes the primary trigger.

```
before each turn:
  if context_length > model_context_window * 0.75:
    trigger compaction before processing
```

### 4.3 Trivial-prompt skip

Skip memory injection for prompts ≤3 tokens (e.g., "ok", "yes", "/status"). Saves ~200-500 tokens on meaningless turns. Check `estimate_message_tokens()` before building memory context.

---

## 5. Implementation Phases

### Phase 1: Foundation (shared infrastructure)

- SQLite + FTS5 session store (`nanobot/session/store.py`)
- Sub-agent loader + runner (`nanobot/agent/subagents.py`)
- Agent file parser (YAML frontmatter + markdown body)
- Delegation tool for main agent
- Migration: JSONL → SQLite on first boot

### Phase 2: Recall agent

- Built-in `nanobot/agents/recall.md`
- `session_search` tool (FTS5-backed, three modes)
- LLM summarization with bounded parallel concurrency
- Session lineage resolution (parent_session_id chains)
- Remove `session_search` schema from main agent's tool list

### Phase 3: Curator agent

- Skill usage telemetry (`.skill_usage.json`)
- Built-in `nanobot/agents/curator.md`
- Idle detection and interval gating
- Phase 1: automatic lifecycle transitions (pure logic)
- Phase 2: umbrella-building LLM pass
- Per-run reports
- Safety guardrails (pinned, agent-created-only, archive-never-delete)

### Phase 4: Optimizations

- Memory context fencing in system prompt
- Context-length-based auto-compact (75% threshold)
- Trivial-prompt skip for memory injection

---

## 6. Token Budget Summary

| Change | Main agent tokens/turn | Offline tokens |
|--------|----------------------|----------------|
| Remove session_search schema from main prompt | **−500** | — |
| Memory fencing in system prompt | **+50** | — |
| Distilled recall summaries vs raw excerpts | **−400** per search | — |
| Trivial-prompt skip | **−200 to −500** on short turns | — |
| Curator Phase 1 (pure logic) | — | 0 |
| Curator Phase 2 (umbrella-building) | — | ~5000 per 7d run (cheap model) |
| Recall summarization | — | ~2000 per search (cheap model) |

**Net:** Main agent saves 450+ tokens/turn (without search) and ~1000 tokens/search. Offline token cost is isolated to cheap models and infrequent (curator: weekly; recall: on-demand).

---

## 7. Files to Protect

### New files
- `nanobot/session/store.py` — SQLite + FTS5 session store
- `nanobot/agent/subagents.py` — agent loader, runner, config
- `nanobot/agent/tools/delegate.py` — delegation tool
- `nanobot/agent/tools/session_search.py` — updated for FTS5 + summarization (moves to recall agent)
- `nanobot/agent/skill_usage.py` — usage telemetry store
- `nanobot/agents/recall.md` — built-in recall agent
- `nanobot/agents/curator.md` — built-in curator agent

### Modified files
- `nanobot/session/search.py` — replaced by `store.py`; keep for migration only
- `nanobot/agent/memory.py` — curator lifecycle integration, Dream stays
- `nanobot/agent/context.py` — memory fencing, trivial-prompt skip
- `nanobot/agent/skill_proposal_metadata.py` — add state field, integrate with skill_usage
- `nanobot/config/schema.py` — subagents config + curator config sections
- `nanobot/agent/loop.py` — delegation dispatch, idle detection for curator
- `nanobot/agent/tools/registry.py` — register delegate tool, remove session_search from main

### Unchanged
- `nanobot/agent/skill_proposals.py` — proposal file store (unchanged)
- `nanobot/skills/scan.py` — skill scan (unchanged)
- `nanobot/doctor/checks/skills.py` — doctor checks (minor update for new states)
- `nanobot/agent/tools/skill_manage.py` — skill_manage stays on main agent for in-session use

---

## 8. Key Decisions

1. **Sub-agent files use markdown + YAML frontmatter** — same pattern as skills for consistency
2. **Curator auto-executes** — no human review gate for consolidations/archiving
3. **Recall is on-demand** — agent calls `delegate(agent="recall", ...)`, not pre-fetched into system prompt
4. **session_search schema removed from main agent** — lives only in recall agent's tool list
5. **Curator runs on idle** — not cron, not in-session. Detected by agent loop when no active conversations.
6. **SQLite + FTS5 replaces JSONL scan** — one-time migration, JSONL kept as backup
7. **Context-length auto-compact at 75%** — matches opencode CLI behavior
8. **Never delete skills** — only archive (recoverable)
