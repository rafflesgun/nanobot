from __future__ import annotations

import json
from pathlib import Path

from nanobot.session.search import SessionSearchService


def _write_session(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_search_returns_ranked_session_hits(tmp_path: Path) -> None:
    _write_session(
        tmp_path / "sessions" / "cli_direct.jsonl",
        [
            {
                "_type": "metadata",
                "metadata": {},
                "created_at": "2026-04-22T09:00:00",
                "updated_at": "2026-04-22T09:10:00",
            },
            {
                "role": "user",
                "content": "Investigate OpenRouter retry loop",
                "timestamp": "2026-04-22T09:01:00",
            },
            {
                "role": "assistant",
                "content": "The retry logic is duplicated in provider retry mode",
                "timestamp": "2026-04-22T09:02:00",
            },
        ],
    )
    _write_session(
        tmp_path / "sessions" / "telegram_foo.jsonl",
        [
            {
                "_type": "metadata",
                "metadata": {},
                "created_at": "2026-04-21T09:00:00",
                "updated_at": "2026-04-21T09:10:00",
            },
            {
                "role": "user",
                "content": "Schedule a reminder for lunch",
                "timestamp": "2026-04-21T09:01:00",
            },
        ],
    )

    service = SessionSearchService(tmp_path)
    hits = service.search("retry loop", limit=3)

    assert len(hits) == 1
    assert hits[0].session_key == "cli:direct"
    assert "retry loop" in hits[0].excerpt.lower()


def test_search_excludes_current_session_when_requested(tmp_path: Path) -> None:
    _write_session(
        tmp_path / "sessions" / "cli_direct.jsonl",
        [
            {
                "_type": "metadata",
                "metadata": {},
                "created_at": "2026-04-22T09:00:00",
                "updated_at": "2026-04-22T09:10:00",
            },
            {
                "role": "user",
                "content": "Find the flaky webhook test",
                "timestamp": "2026-04-22T09:01:00",
            },
        ],
    )

    service = SessionSearchService(tmp_path)
    hits = service.search("flaky webhook", exclude_session_key="cli:direct")

    assert hits == []


def test_search_skips_corrupt_rows_and_metadata(tmp_path: Path) -> None:
    path = tmp_path / "sessions" / "cli_direct.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"_type":"metadata","metadata":{}}\n'
        '{"role":"user","content":"remember nginx timeout","timestamp":"2026-04-22T09:01:00"}\n'
        "{bad json}\n",
        encoding="utf-8",
    )

    service = SessionSearchService(tmp_path)
    hits = service.search("nginx timeout")

    assert len(hits) == 1
    assert hits[0].match_count >= 1


def test_search_returns_empty_for_blank_query(tmp_path: Path) -> None:
    service = SessionSearchService(tmp_path)

    assert service.search("   ") == []


def test_search_uses_metadata_key_for_topic_sessions(tmp_path: Path) -> None:
    _write_session(
        tmp_path / "sessions" / "telegram_123_topic_42.jsonl",
        [
            {
                "_type": "metadata",
                "metadata": {},
                "key": "telegram:123:topic:42",
                "created_at": "2026-04-22T09:00:00",
                "updated_at": "2026-04-22T09:10:00",
            },
            {
                "role": "user",
                "content": "Topic-specific retry incident",
                "timestamp": "2026-04-22T09:01:00",
            },
        ],
    )

    service = SessionSearchService(tmp_path)
    hits = service.search("retry incident")

    assert len(hits) == 1
    assert hits[0].session_key == "telegram:123:topic:42"


def test_search_excludes_current_topic_session_using_metadata_key(tmp_path: Path) -> None:
    _write_session(
        tmp_path / "sessions" / "telegram_123_topic_42.jsonl",
        [
            {
                "_type": "metadata",
                "metadata": {},
                "key": "telegram:123:topic:42",
                "created_at": "2026-04-22T09:00:00",
                "updated_at": "2026-04-22T09:10:00",
            },
            {
                "role": "user",
                "content": "Topic-specific retry incident",
                "timestamp": "2026-04-22T09:01:00",
            },
        ],
    )

    service = SessionSearchService(tmp_path)
    hits = service.search("retry incident", exclude_session_key="telegram:123:topic:42")

    assert hits == []
