from __future__ import annotations

import json

import pytest

from nanobot.agent.tools.session_search import SessionSearchTool


@pytest.mark.asyncio
async def test_session_search_tool_formats_hits(tmp_path) -> None:
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "cli_direct.jsonl").write_text(
        '{"_type":"metadata","metadata":{},"key":"cli:direct"}\n'
        '{"role":"user","content":"Investigate retry loop","timestamp":"2026-04-22T09:01:00"}\n',
        encoding="utf-8",
    )

    tool = SessionSearchTool(workspace=tmp_path)
    tool.set_context(session_key="telegram:123")
    result = await tool.execute(query="retry loop", limit=3)

    assert "Session recall" in result
    assert "cli:direct" in result


@pytest.mark.asyncio
async def test_session_search_tool_rejects_blank_query(tmp_path) -> None:
    tool = SessionSearchTool(workspace=tmp_path)
    result = await tool.execute(query="  ")

    assert result == "Error: query cannot be empty"
