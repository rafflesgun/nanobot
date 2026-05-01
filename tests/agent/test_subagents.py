"""Tests for sub-agent loading and running."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from nanobot.agent.subagents import AgentLoader, AgentConfig


@pytest.fixture
def agents_dir(tmp_path: Path) -> Path:
    d = tmp_path / "agents"
    d.mkdir()
    return d


class TestAgentLoader:
    def test_load_agent_from_md_file(self, agents_dir: Path) -> None:
        md = agents_dir / "test-agent.md"
        md.write_text(textwrap.dedent("""\
            ---
            name: test-agent
            description: A test agent for unit tests
            model: openai/gpt-4o-mini
            temperature: 0.1
            tools:
              - read_file
              - shell
            max_iterations: 5
            max_tokens: 4000
            trigger: on_demand
            ---
            You are a test agent. Do test things.
        """))

        loader = AgentLoader(agents_dir)
        config = loader.load("test-agent")
        assert config is not None
        assert config.name == "test-agent"
        assert config.description == "A test agent for unit tests"
        assert config.model == "openai/gpt-4o-mini"
        assert config.temperature == 0.1
        assert config.tools == ["read_file", "shell"]
        assert config.max_iterations == 5
        assert config.max_tokens == 4000
        assert config.trigger == "on_demand"
        assert "You are a test agent" in config.system_prompt

    def test_load_nonexistent_agent_returns_none(self, agents_dir: Path) -> None:
        loader = AgentLoader(agents_dir)
        assert loader.load("does-not-exist") is None

    def test_default_values_for_optional_fields(self, agents_dir: Path) -> None:
        md = agents_dir / "minimal.md"
        md.write_text(textwrap.dedent("""\
            ---
            name: minimal
            description: Minimal agent
            ---
            Just do it.
        """))

        loader = AgentLoader(agents_dir)
        config = loader.load("minimal")
        assert config is not None
        assert config.model == ""
        assert config.temperature == 0.0
        assert config.tools == []
        assert config.max_iterations == 3
        assert config.max_tokens == 4096
        assert config.trigger == "on_demand"

    def test_list_agents(self, agents_dir: Path) -> None:
        (agents_dir / "a.md").write_text("---\nname: a\ndescription: Agent A\n---\nA")
        (agents_dir / "b.md").write_text("---\nname: b\ndescription: Agent B\n---\nB")
        (agents_dir / "not-md.txt").write_text("not an agent")

        loader = AgentLoader(agents_dir)
        agents = loader.list_all()
        assert len(agents) == 2
        names = {a.name for a in agents}
        assert names == {"a", "b"}

    def test_workspace_agent_overrides_builtin(self, tmp_path: Path) -> None:
        builtin = tmp_path / "builtin"
        builtin.mkdir()
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        (builtin / "recall.md").write_text(
            "---\nname: recall\ndescription: Builtin recall\nmodel: gpt-4o-mini\n---\nBuiltin recall."
        )
        (workspace / "recall.md").write_text(
            "---\nname: recall\ndescription: Custom recall\nmodel: gpt-3.5-turbo\n---\nCustom recall."
        )

        loader = AgentLoader(workspace, builtin_dir=builtin)
        config = loader.load("recall")
        assert config is not None
        assert config.model == "gpt-3.5-turbo"
        assert "Custom recall" in config.system_prompt

    def test_config_overrides_frontmatter(self, agents_dir: Path) -> None:
        (agents_dir / "test-agent.md").write_text(textwrap.dedent("""\
            ---
            name: test-agent
            description: Test
            model: gpt-4o-mini
            temperature: 0.1
            ---
            Test body.
        """))

        loader = AgentLoader(agents_dir)
        config = loader.load("test-agent", overrides={"model": "gemini-flash", "temperature": 0.5})
        assert config is not None
        assert config.model == "gemini-flash"
        assert config.temperature == 0.5
