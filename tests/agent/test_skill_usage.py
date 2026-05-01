"""Tests for skill usage telemetry."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nanobot.agent.skill_usage import SkillUsageStore


@pytest.fixture
def usage_file(tmp_path: Path) -> Path:
    return tmp_path / ".skill_usage.json"


@pytest.fixture
def store(usage_file: Path) -> SkillUsageStore:
    return SkillUsageStore(usage_file)


class TestSkillUsageStore:
    def test_bump_use_creates_record(self, store: SkillUsageStore) -> None:
        store.bump_use("my-skill")
        record = store.get("my-skill")
        assert record is not None
        assert record["use_count"] == 1
        assert record["state"] == "active"
        assert record["last_used_at"] is not None

    def test_bump_patch_increments_counter(self, store: SkillUsageStore) -> None:
        store.bump_patch("my-skill")
        store.bump_patch("my-skill")
        record = store.get("my-skill")
        assert record["patch_count"] == 2

    def test_bump_view_increments_view_count(self, store: SkillUsageStore) -> None:
        store.bump_view("my-skill")
        store.bump_view("my-skill")
        store.bump_view("my-skill")
        record = store.get("my-skill")
        assert record["view_count"] == 3

    def test_set_state_transitions(self, store: SkillUsageStore) -> None:
        store.bump_use("my-skill")
        store.set_state("my-skill", "stale")
        assert store.get("my-skill")["state"] == "stale"

    def test_set_state_invalid_raises(self, store: SkillUsageStore) -> None:
        store.bump_use("my-skill")
        with pytest.raises(ValueError, match="invalid"):
            store.set_state("my-skill", "deleted")

    def test_pinned_skill_flag(self, store: SkillUsageStore) -> None:
        store.bump_use("my-skill")
        store.set_pinned("my-skill", True)
        assert store.get("my-skill")["pinned"] is True
        store.set_pinned("my-skill", False)
        assert store.get("my-skill")["pinned"] is False

    def test_latest_activity_at(self, store: SkillUsageStore) -> None:
        store.bump_use("s1")
        store.bump_patch("s1")
        record = store.get("s1")
        latest = store.latest_activity_at(record)
        assert latest is not None

    def test_get_nonexistent_returns_none(self, store: SkillUsageStore) -> None:
        assert store.get("does-not-exist") is None
