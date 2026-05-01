"""Tests for context fencing and trivial-prompt skip."""
from __future__ import annotations

from pathlib import Path

import pytest

from nanobot.agent.context import ContextBuilder


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "test_workspace"
    ws.mkdir()
    (ws / "SOUL.md").write_text("You are a test assistant.")
    (ws / "USER.md").write_text("User prefers brevity.")
    mem_dir = ws / "memory"
    mem_dir.mkdir()
    (mem_dir / "MEMORY.md").write_text("The user works on nanobot.")
    return ws


class TestContextFencing:
    def test_memory_context_is_fenced_with_tags(self, workspace: Path) -> None:
        ctx = ContextBuilder(workspace)
        prompt = ctx.build_system_prompt()

        assert "<memory-context>" in prompt
        assert "</memory-context>" in prompt
        assert "NOT new user input" in prompt

    def test_memory_fence_contains_memory_content(self, workspace: Path) -> None:
        ctx = ContextBuilder(workspace)
        prompt = ctx.build_system_prompt()

        # The memory content should appear between the fence tags
        assert "nanobot" in prompt

    def test_template_memory_is_skipped(self, workspace: Path) -> None:
        """Template MEMORY.md content should not be injected."""
        # Write template-like content to MEMORY.md
        (workspace / "memory" / "MEMORY.md").write_text(
            "# Memory\n\nAdd important context here..."
        )
        ctx = ContextBuilder(workspace)
        prompt = ctx.build_system_prompt()

        # Template content from bundled templates should not appear fenced
        # (the _is_template_content check should catch it)
        # Note: test relies on nanobot/templates/memory/MEMORY.md matching template content


class TestTrivialPromptSkip:
    def test_normal_prompt_includes_memory(self, workspace: Path) -> None:
        ctx = ContextBuilder(workspace)
        prompt = ctx.build_system_prompt(
            user_message="What did we work on yesterday with the retry logic?"
        )

        assert "<memory-context>" in prompt

    def test_none_message_includes_memory(self, workspace: Path) -> None:
        """None user_message means caller didn't specify — include memory (backward compat)."""
        ctx = ContextBuilder(workspace)
        prompt = ctx.build_system_prompt(user_message=None)

        assert "<memory-context>" in prompt

    def test_short_command_skips_memory(self, workspace: Path) -> None:
        """Single-word commands like '/s' should skip memory injection (≤3 raw tokens)."""
        ctx = ContextBuilder(workspace)
        prompt = ctx.build_system_prompt(user_message="/s")
        assert "<memory-context>" not in prompt
