"""Tests for SessionSearchTool using SessionStore (SQLite FTS5)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from nanobot.agent.tools.session_search import SessionSearchTool
from nanobot.session.store import SessionStore


def _make_store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path / "state.db")


def _add_session(store: SessionStore, session_id: str, **kwargs: str) -> None:
    now = kwargs.get("started_at", "2026-04-22T09:00:00")
    store.create_session(
        session_id=session_id,
        source=kwargs.get("source", "cli"),
        model=kwargs.get("model", "gpt-4o"),
        started_at=now,
    )


def _add_message(store: SessionStore, session_id: str, role: str, content: str, ts: str = "") -> None:
    if not ts:
        ts = f"2026-04-22T09:0{time.time() % 60:02.0f}:00"
    store.add_message(session_id, role, content, ts)


def test_search_returns_ranked_session_hits(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _add_session(store, "cli_direct")
    _add_message(store, "cli_direct", "user", "Investigate OpenRouter retry loop")
    _add_message(store, "cli_direct", "assistant", "The retry logic is duplicated in provider retry mode")

    _add_session(store, "telegram_foo")
    _add_message(store, "telegram_foo", "user", "Schedule a reminder for lunch")

    tool = SessionSearchTool(store)
    result = json.loads(tool._keyword_search("retry loop", 3))

    assert result["success"] is True
    assert result["count"] == 1
    assert result["results"][0]["session_id"] == "cli_direct"


def test_recent_sessions_browse(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _add_session(store, "a", started_at="2026-04-22T09:00:00")
    _add_message(store, "a", "user", "Hello")
    _add_session(store, "b", started_at="2026-04-23T10:00:00")
    _add_message(store, "b", "user", "World")

    tool = SessionSearchTool(store)
    result = json.loads(tool._recent_sessions(5))

    assert result["success"] is True
    assert result["mode"] == "recent"
    assert result["count"] >= 2
    session_ids = {r["session_id"] for r in result["results"]}
    assert "a" in session_ids
    assert "b" in session_ids


def test_empty_query_returns_recent(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _add_session(store, "s1", started_at="2026-04-22T09:00:00")
    _add_message(store, "s1", "user", "Test message")

    tool = SessionSearchTool(store)
    result_str = tool._recent_sessions(3)
    result = json.loads(result_str)

    assert result["mode"] == "recent"


def test_keyword_search_no_results(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _add_session(store, "s1")
    _add_message(store, "s1", "user", "Hello world")

    tool = SessionSearchTool(store)
    result_str = tool._keyword_search("nonexistent_xyz", 3)
    result = json.loads(result_str)

    assert result["success"] is True
    assert result["count"] == 0


def test_excludes_current_session(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _add_session(store, "cli_direct")
    _add_message(store, "cli_direct", "user", "Find the flaky webhook test")

    tool = SessionSearchTool(store)
    tool.set_context(session_key="cli_direct")
    result_str = tool._keyword_search("flaky webhook", 3)
    result = json.loads(result_str)

    assert result["count"] == 0  # current session excluded


def test_multipart_content_searchable(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    _add_session(store, "cli_direct")
    _add_message(store, "cli_direct", "assistant", "The retry logic is duplicated in provider retry mode")

    tool = SessionSearchTool(store)
    result_str = tool._keyword_search("retry logic", 3)
    result = json.loads(result_str)

    assert result["count"] == 1
    assert result["results"][0]["session_id"] == "cli_direct"


def test_limit_enforced(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    for i in range(10):
        sid = f"s{i}"
        _add_session(store, sid)
        _add_message(store, sid, "user", f"Test message about retry loop number {i}")

    tool = SessionSearchTool(store)
    result_str = tool._keyword_search("retry loop", 3)
    result = json.loads(result_str)

    assert result["count"] <= 3


def test_tool_name_and_schema(tmp_path: Path) -> None:
    store = _make_store(tmp_path)
    tool = SessionSearchTool(store)

    assert tool.name == "session_search"
    assert tool.read_only is True
    params = tool.parameters
    assert "query" in params["properties"]
    assert params["required"] == []
