"""Tests for SQLite session store."""
from __future__ import annotations

from pathlib import Path

import pytest

from nanobot.session.store import SessionStore


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_state.db"


@pytest.fixture
def store(db_path: Path) -> SessionStore:
    return SessionStore(db_path)


class TestSessionCRUD:
    def test_create_and_get_session(self, store: SessionStore) -> None:
        store.create_session(
            session_id="test-key",
            source="cli",
            model="test-model",
            started_at="2026-05-01T10:00:00Z",
        )
        session = store.get_session("test-key")
        assert session is not None
        assert session["id"] == "test-key"
        assert session["source"] == "cli"
        assert session["model"] == "test-model"

    def test_get_nonexistent_session_returns_none(self, store: SessionStore) -> None:
        assert store.get_session("does-not-exist") is None

    def test_add_message_and_search(self, store: SessionStore) -> None:
        store.create_session(
            session_id="test-key",
            source="cli",
            model="test-model",
            started_at="2026-05-01T10:00:00Z",
        )
        store.add_message(
            session_id="test-key",
            role="user",
            content="I need to fix the retry loop in the gateway",
            timestamp="2026-05-01T10:01:00Z",
        )
        store.add_message(
            session_id="test-key",
            role="assistant",
            content="Let me look at the retry logic in the connection handler",
            timestamp="2026-05-01T10:02:00Z",
        )

        results = store.search_messages("retry loop", limit=5)
        assert len(results) == 2
        assert results[0]["session_id"] == "test-key"

    def test_search_returns_results_ranked_by_relevance(self, store: SessionStore) -> None:
        store.create_session("s1", "cli", "m", "2026-05-01T10:00:00Z")
        store.create_session("s2", "cli", "m", "2026-05-02T10:00:00Z")

        # s1: exact match, should rank higher
        store.add_message("s1", "user", "I need to fix the retry loop", "2026-05-01T10:01:00Z")
        # s2: partial match
        store.add_message("s2", "user", "The loop runs slowly on retry", "2026-05-02T10:01:00Z")

        results = store.search_messages("retry loop", limit=5)
        assert len(results) >= 2
        # s1 should appear first
        assert results[0]["session_id"] == "s1"

    def test_list_sessions_rich(self, store: SessionStore) -> None:
        store.create_session("s1", "cli", "m1", "2026-05-01T10:00:00Z")
        store.add_message("s1", "user", "hello", "2026-05-01T10:01:00Z")
        store.create_session("s2", "telegram", "m2", "2026-05-02T10:00:00Z")
        store.add_message("s2", "user", "world", "2026-05-02T10:01:00Z")
        store.add_message("s2", "assistant", "hi there", "2026-05-02T10:02:00Z")

        sessions = store.list_sessions_rich(limit=5)
        assert len(sessions) == 2
        assert sessions[0]["message_count"] == 2  # s2 is newer
        assert sessions[1]["message_count"] == 1

    def test_update_session_title(self, store: SessionStore) -> None:
        store.create_session("s1", "cli", "m", "2026-05-01T10:00:00Z")
        store.update_session("s1", title="Fix retry loop")
        session = store.get_session("s1")
        assert session["title"] == "Fix retry loop"

    def test_parent_session_lineage_stored(self, store: SessionStore) -> None:
        store.create_session("parent", "cli", "m", "2026-05-01T10:00:00Z")
        store.create_session(
            "child", "cli", "m", "2026-05-01T11:00:00Z", parent_session_id="parent"
        )
        child = store.get_session("child")
        assert child["parent_session_id"] == "parent"


class TestMigration:
    def test_migrate_from_jsonl(self, tmp_path: Path, db_path: Path) -> None:
        sessions_dir = tmp_path / "sessions"
        sessions_dir.mkdir()
        jsonl = sessions_dir / "test-key.jsonl"
        jsonl.write_text(
            '{"_type": "metadata", "key": "test-key"}\n'
            '{"role": "user", "content": "hello migration", "timestamp": "2026-05-01T10:00:00Z"}\n'
        )

        store = SessionStore(db_path)
        migrated = store.migrate_from_jsonl(sessions_dir)
        assert migrated > 0

        results = store.search_messages("migration", limit=3)
        assert len(results) == 1
