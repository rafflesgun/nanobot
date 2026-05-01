"""Tests for the delegate tool."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from nanobot.agent.subagents import AgentLoader
from nanobot.agent.tools.delegate import DelegateTool


@pytest.fixture
def agents_dir(tmp_path: Path) -> Path:
    d = tmp_path / "agents"
    d.mkdir()
    (d / "recall.md").write_text(textwrap.dedent("""\
        ---
        name: recall
        description: Search past sessions
        model: gpt-4o-mini
        tools:
          - session_search
        ---
        You are a recall agent. Search and summarize.
    """))
    return d


@pytest.fixture
def tool(agents_dir: Path) -> DelegateTool:
    loader = AgentLoader(agents_dir)
    return DelegateTool(loader, provider=None)


class TestDelegateTool:
    def test_name_and_schema(self, tool: DelegateTool) -> None:
        assert tool.name == "delegate"
        params = tool.parameters
        assert "agent" in params["properties"]
        assert "task" in params["properties"]
        assert params["required"] == ["agent", "task"]

    def test_nonexistent_agent_returns_error(self, tool: DelegateTool) -> None:
        assert "Error" in tool.execute_sync("nonexistent", "do something")

    def test_valid_agent_sync_response(self, tool: DelegateTool) -> None:
        result = tool.execute_sync("recall", "find past conversations about retry")
        assert "recall" in result

    def test_cumulative_usage_starts_empty(self, tool: DelegateTool) -> None:
        assert tool.cumulative_usage == {}

    def test_cumulative_usage_is_mutable(self, tool: DelegateTool) -> None:
        tool.cumulative_usage["prompt_tokens"] = 100
        tool.cumulative_usage["cached_tokens"] = 80
        assert tool.cumulative_usage["prompt_tokens"] == 100
        assert tool.cumulative_usage["cached_tokens"] == 80
