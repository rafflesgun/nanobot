"""Tests for StatsManager token tracking."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from nanobot.utils.stats import StatsManager


@pytest.fixture
def stats_dir(tmp_path: Path) -> Path:
    return tmp_path / "stats"


@pytest.fixture
def manager(stats_dir: Path) -> StatsManager:
    workspace = stats_dir.parent
    (workspace / "stats").mkdir(parents=True, exist_ok=True)
    mgr = StatsManager(workspace)
    mgr.usage_file = stats_dir / "usage.jsonl"
    return mgr


class TestStatsManager:
    def test_record_and_get_stats(self, manager: StatsManager) -> None:
        manager.record_usage(
            channel="telegram",
            chat_id="123",
            model="deepseek-v4",
            input_tokens=1000,
            output_tokens=200,
            total_tokens=1200,
            session_key="telegram:123",
            cached_tokens=800,
        )

        stats = manager.get_stats(channel="telegram", chat_id="123")
        assert stats["total_input_tokens"] == 1000
        assert stats["total_output_tokens"] == 200
        assert stats["total_tokens"] == 1200
        assert stats["total_cached_tokens"] == 800
        assert stats["count"] == 1

    def test_get_stats_filters_by_channel(self, manager: StatsManager) -> None:
        manager.record_usage("telegram", "123", "m", 100, 50, 150, "k1")
        manager.record_usage("cli", "direct", "m", 200, 100, 300, "k2")

        tg_stats = manager.get_stats(channel="telegram")
        assert tg_stats["count"] == 1
        assert tg_stats["total_input_tokens"] == 100

        cli_stats = manager.get_stats(channel="cli")
        assert cli_stats["count"] == 1
        assert cli_stats["total_input_tokens"] == 200

    def test_cached_tokens_persisted_in_jsonl(self, manager: StatsManager) -> None:
        manager.record_usage(
            "cli", "direct", "deepseek", 1000, 200, 1200, "key",
            cached_tokens=800,
        )

        lines = manager.usage_file.read_text().strip().split("\n")
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["cached_tokens"] == 800

    def test_cached_tokens_zero_not_stored(self, manager: StatsManager) -> None:
        manager.record_usage("cli", "direct", "m", 100, 50, 150, "key", cached_tokens=0)
        lines = manager.usage_file.read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert "cached_tokens" not in entry

    def test_aggregate_by_channel_includes_cached(self, manager: StatsManager) -> None:
        manager.record_usage("telegram", "123", "m", 1000, 200, 1200, "k1", cached_tokens=800)
        manager.record_usage("telegram", "456", "m", 500, 100, 600, "k2", cached_tokens=300)

        totals = manager.get_total_stats()
        tg = totals["telegram"]
        assert tg["total_input_tokens"] == 1500
        assert tg["total_cached_tokens"] == 1100
