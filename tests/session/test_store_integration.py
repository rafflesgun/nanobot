"""Integration tests for SessionManager + SessionStore."""
from __future__ import annotations

from pathlib import Path
import tempfile

import pytest

from nanobot.session.manager import SessionManager
from nanobot.session.store import SessionStore


@pytest.fixture
def workspace():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


def test_session_manager_creates_store(workspace):
    mgr = SessionManager(workspace)
    assert mgr.store is not None
    assert isinstance(mgr.store, SessionStore)


def test_session_manager_migrates_jsonl(workspace):
    sessions_dir = workspace / "sessions"
    sessions_dir.mkdir(parents=True)
    jsonl = sessions_dir / "test-key.jsonl"
    jsonl.write_text(
        '{"_type": "metadata", "key": "test-key"}\n'
        '{"role": "user", "content": "hello world", "timestamp": "2026-05-01T10:00:00Z"}\n'
    )

    mgr = SessionManager(workspace)
    mgr._maybe_migrate()

    results = mgr.store.search_messages("hello world", limit=3)
    assert len(results) == 1
    assert results[0]["session_id"] == "test-key"


def test_session_manager_migration_is_idempotent(workspace):
    sessions_dir = workspace / "sessions"
    sessions_dir.mkdir(parents=True)
    jsonl = sessions_dir / "s1.jsonl"
    jsonl.write_text(
        '{"_type": "metadata", "key": "s1"}\n'
        '{"role": "user", "content": "test message", "timestamp": "2026-05-01T10:00:00Z"}\n'
    )

    mgr = SessionManager(workspace)
    mgr._maybe_migrate()
    assert (sessions_dir / ".sqlite_migrated").exists()

    # Second call should be a no-op
    mgr._maybe_migrate()
    results = mgr.store.search_messages("test message", limit=3)
    assert len(results) == 1
