"""Tests for curator scheduler."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nanobot.agent.skill_usage import SkillUsageStore, STATE_ACTIVE, STATE_STALE, STATE_ARCHIVED
from nanobot.agent.curator import CuratorScheduler


@pytest.fixture
def usage_store(tmp_path: Path) -> SkillUsageStore:
    return SkillUsageStore(tmp_path / ".skill_usage.json")


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / ".curator_state"


@pytest.fixture
def scheduler(state_path: Path, usage_store: SkillUsageStore) -> CuratorScheduler:
    return CuratorScheduler(state_path, usage_store)


class TestCuratorScheduler:
    def test_should_run_when_never_ran(self, scheduler: CuratorScheduler) -> None:
        assert scheduler.should_run()

    def test_should_not_run_immediately_after_mark_ran(self, scheduler: CuratorScheduler) -> None:
        scheduler.mark_ran()
        assert not scheduler.should_run()

    def test_should_run_after_interval_elapsed(self, scheduler: CuratorScheduler) -> None:
        scheduler.mark_ran()
        future = datetime.now(timezone.utc) + timedelta(days=8)
        assert scheduler.should_run(now=future)

    def test_mark_ran_increments_count(self, scheduler: CuratorScheduler) -> None:
        scheduler.mark_ran()
        scheduler.mark_ran()
        state = scheduler._load_state()
        assert state["run_count"] == 2


class TestLifecycleTransitions:
    def test_active_skill_with_recent_activity_stays_active(
        self, scheduler: CuratorScheduler, usage_store: SkillUsageStore
    ) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        usage_store.bump_use("skill-a")
        # Force the timestamp to be recent
        usage_store._read()["skill-a"]["last_used_at"] = now.isoformat()

        counts = scheduler.apply_lifecycle(now=now)
        assert counts["checked"] == 1
        assert counts["marked_stale"] == 0
        assert usage_store.get("skill-a")["state"] == STATE_ACTIVE

    def test_marks_stale_when_unused_past_threshold(
        self, scheduler: CuratorScheduler, usage_store: SkillUsageStore
    ) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        usage_store.bump_use("skill-a")
        # 40 days ago — must write back to persist
        data = usage_store._read()
        data["skill-a"]["last_used_at"] = (now - timedelta(days=40)).isoformat()
        usage_store._write(data)

        counts = scheduler.apply_lifecycle(now=now)
        assert counts["marked_stale"] == 1
        assert usage_store.get("skill-a")["state"] == STATE_STALE

    def test_archives_when_unused_past_archive_threshold(
        self, scheduler: CuratorScheduler, usage_store: SkillUsageStore
    ) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        usage_store.bump_use("skill-a")
        # 100 days ago
        data = usage_store._read()
        data["skill-a"]["last_used_at"] = (now - timedelta(days=100)).isoformat()
        usage_store._write(data)

        counts = scheduler.apply_lifecycle(now=now)
        assert counts["archived"] == 1
        assert usage_store.get("skill-a")["state"] == STATE_ARCHIVED

    def test_reactivates_stale_skill_when_used_again(
        self, scheduler: CuratorScheduler, usage_store: SkillUsageStore
    ) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        usage_store.bump_use("skill-a")
        usage_store.set_state("skill-a", STATE_STALE)
        # Recent activity
        usage_store._read()["skill-a"]["last_used_at"] = now.isoformat()

        counts = scheduler.apply_lifecycle(now=now)
        assert counts["reactivated"] == 1
        assert usage_store.get("skill-a")["state"] == STATE_ACTIVE

    def test_pinned_skill_bypasses_all_transitions(
        self, scheduler: CuratorScheduler, usage_store: SkillUsageStore
    ) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        usage_store.bump_use("skill-a")
        usage_store.set_pinned("skill-a", True)
        # 100 days ago — should archive but pinned
        usage_store._read()["skill-a"]["last_used_at"] = (
            now - timedelta(days=100)
        ).isoformat()

        counts = scheduler.apply_lifecycle(now=now)
        assert counts["archived"] == 0
        assert usage_store.get("skill-a")["state"] == STATE_ACTIVE

    def test_skill_with_no_activity_uses_created_at(
        self, scheduler: CuratorScheduler, usage_store: SkillUsageStore
    ) -> None:
        now = datetime(2026, 5, 1, tzinfo=timezone.utc)
        # Create a skill with no bump_use (simulates Dream-created but never used)
        usage_store._ensure_record("skill-a")
        data = usage_store._read()
        data["skill-a"]["created_at"] = (now - timedelta(days=100)).isoformat()
        usage_store._write(data)

        counts = scheduler.apply_lifecycle(now=now)
        assert counts["archived"] == 1
