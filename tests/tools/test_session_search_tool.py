from __future__ import annotations

import json

import pytest

from nanobot.agent.tools.session_search import SessionSearchTool
from nanobot.session.store import SessionStore


@pytest.mark.asyncio
async def test_session_search_tool_formats_hits(tmp_path) -> None:
    store = SessionStore(tmp_path / "test.db")
    store.create_session("cli:direct", "cli", "test-model", "2026-04-22T09:00:00")
    store.add_message(
        "cli:direct", "user", "Investigate retry loop", "2026-04-22T09:01:00"
    )

    tool = SessionSearchTool(store=store)
    tool.set_context(session_key="telegram:123")
    result = await tool.execute(query="retry loop", limit=3)
    data = json.loads(result)

    assert data["success"]
    assert data["mode"] == "keyword"
    assert len(data["results"]) == 1
    assert data["results"][0]["session_id"] == "cli:direct"


@pytest.mark.asyncio
async def test_session_search_tool_blank_query_browses_recent(tmp_path) -> None:
    store = SessionStore(tmp_path / "test.db")
    tool = SessionSearchTool(store=store)
    result = await tool.execute(query="  ")
    data = json.loads(result)

    assert data["success"]
    assert data["mode"] == "recent"  # empty queries now browse recent sessions
