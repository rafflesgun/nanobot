"""Curator — idle-triggered skill lifecycle manager."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from nanobot.agent.skill_usage import SkillUsageStore, STATE_ACTIVE, STATE_STALE, STATE_ARCHIVED

if TYPE_CHECKING:
    from nanobot.agent.subagents import AgentLoader

logger = logging.getLogger(__name__)

DEFAULT_INTERVAL_HOURS = 24 * 7
DEFAULT_MIN_IDLE_HOURS = 2
DEFAULT_STALE_AFTER_DAYS = 30
DEFAULT_ARCHIVE_AFTER_DAYS = 90


class CuratorScheduler:
    def __init__(self, state_path: Path, usage_store: SkillUsageStore) -> None:
        self._state_path = state_path
        self._usage = usage_store

    def should_run(self, now: datetime | None = None) -> bool:
        if now is None:
            now = datetime.now(timezone.utc)
        state = self._load_state()
        last = state.get("last_run_at")
        if last is None:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
        except (TypeError, ValueError):
            return True
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        interval = timedelta(hours=DEFAULT_INTERVAL_HOURS)
        return (now - last_dt) >= interval

    def mark_ran(self) -> None:
        state = self._load_state()
        state["last_run_at"] = datetime.now(timezone.utc).isoformat()
        state["run_count"] = state.get("run_count", 0) + 1
        self._save_state(state)
        logger.info("Curator marked as ran (count=%d)", state["run_count"])

    def apply_lifecycle(self, now: datetime | None = None) -> dict[str, int]:
        """Phase 1: automatic state transitions (pure logic, zero LLM tokens)."""
        if now is None:
            now = datetime.now(timezone.utc)
        stale_cutoff = now - timedelta(days=DEFAULT_STALE_AFTER_DAYS)
        archive_cutoff = now - timedelta(days=DEFAULT_ARCHIVE_AFTER_DAYS)

        counts = {"checked": 0, "marked_stale": 0, "archived": 0, "reactivated": 0}

        data = self._usage._read()
        for name, rec in data.items():
            counts["checked"] += 1
            if rec.get("pinned"):
                continue

            last_activity = self._usage.latest_activity_at(rec)
            anchor = last_activity or rec.get("created_at") or now.isoformat()
            try:
                anchor_dt = datetime.fromisoformat(str(anchor))
            except (TypeError, ValueError):
                continue
            if anchor_dt.tzinfo is None:
                anchor_dt = anchor_dt.replace(tzinfo=timezone.utc)

            current = rec.get("state", STATE_ACTIVE)

            if anchor_dt <= archive_cutoff and current != STATE_ARCHIVED:
                self._usage.set_state(name, STATE_ARCHIVED)
                counts["archived"] += 1
            elif anchor_dt <= stale_cutoff and current == STATE_ACTIVE:
                self._usage.set_state(name, STATE_STALE)
                counts["marked_stale"] += 1
            elif anchor_dt > stale_cutoff and current == STATE_STALE:
                self._usage.set_state(name, STATE_ACTIVE)
                counts["reactivated"] += 1

        return counts

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {}
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, data: dict[str, Any]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._state_path.parent), prefix=".curator_state_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._state_path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # -- Phase 2 --------------------------------------------------------------

    async def run_umbrella_building(
        self,
        loader: "AgentLoader",
        provider: Any,
        workspace: Path,
    ) -> dict[str, Any]:
        """Phase 2: LLM-driven umbrella-building consolidation."""
        from nanobot.agent.runner import AgentRunner, AgentRunSpec
        from nanobot.agent.tools.registry import ToolRegistry

        config = loader.load("curator")
        if config is None:
            return {"error": "curator agent not found"}

        tools = ToolRegistry()
        from nanobot.agent.loop import get_tool_factories
        factories = get_tool_factories()
        for tool_name in config.tools:
            factory = factories.get(tool_name)
            if factory:
                tools.register(factory())

        skills_text = self._list_agent_skills(workspace)

        spec = AgentRunSpec(
            initial_messages=[
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": f"## Candidate Skills\n\n{skills_text}"},
            ],
            tools=tools,
            model=config.model,
            max_iterations=config.max_iterations,
            max_tool_result_chars=16_000,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        runner = AgentRunner(provider)
        result = await runner.run(spec)
        logger.info(
            "Curator Phase 2 complete: stop_reason=%s, tool_events=%d",
            result.stop_reason,
            len(result.tool_events or []),
        )
        return {
            "stop_reason": result.stop_reason,
            "final_content": result.final_content,
            "tool_events": result.tool_events,
        }

    def _list_agent_skills(self, workspace: Path) -> str:
        import re as _re
        _DESC_RE = _re.compile(r"^description:\s*(.+)$", _re.MULTILINE | _re.IGNORECASE)
        lines: list[str] = []
        skills_dir = workspace / "skills"
        for d in sorted(skills_dir.iterdir()) if skills_dir.exists() else []:
            if not d.is_dir():
                continue
            skill_md = d / "SKILL.md"
            if not skill_md.exists():
                continue
            content = skill_md.read_text(encoding="utf-8")[:500]
            m = _DESC_RE.search(content)
            desc = m.group(1).strip() if m else "(no description)"
            usage = self._usage.get(d.name) or {}
            lines.append(
                f"- {d.name} — {desc} "
                f"(state={usage.get('state', 'active')}, "
                f"use_count={usage.get('use_count', 0)}, "
                f"pinned={usage.get('pinned', False)})"
            )
        return "\n".join(lines) if lines else "(no agent-created skills)"
