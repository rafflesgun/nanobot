from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from nanobot.bus.events import InboundMessage
from nanobot.command.builtin import cmd_workflow
from nanobot.command.router import CommandContext


def write_workflow(workspace: Path) -> None:
    workflows_dir = workspace / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "release-check.md").write_text(
        """---
name: release-check
description: Pre-release validation checklist
---

1. Run doctor.
2. Summarize risks.
""",
        encoding="utf-8",
    )


def write_invalid_workflow(workspace: Path) -> None:
    workflows_dir = workspace / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "broken.md").write_text("not frontmatter", encoding="utf-8")


def workflow_context(tmp_path: Path, raw: str, args: str) -> CommandContext:
    msg = InboundMessage(
        channel="cli",
        sender_id="u1",
        chat_id="direct",
        content=raw,
        metadata={"message_thread_id": "thread-1"},
    )
    return CommandContext(
        msg=msg,
        session=None,
        key=msg.session_key,
        raw=raw,
        args=args,
        loop=SimpleNamespace(workspace=tmp_path),
    )


@pytest.mark.asyncio
async def test_workflow_list_returns_text_metadata_and_step_count(tmp_path) -> None:
    write_workflow(tmp_path)
    write_invalid_workflow(tmp_path)

    out = await cmd_workflow(workflow_context(tmp_path, "/workflow list", "list"))

    assert out.metadata["render_as"] == "text"
    assert out.metadata["message_thread_id"] == "thread-1"
    assert out.metadata["command_response"] is True
    assert "release-check" in out.content
    assert "2 steps" in out.content
    assert "broken" in out.content


@pytest.mark.asyncio
async def test_workflow_show_returns_full_instruction_workflow(tmp_path) -> None:
    write_workflow(tmp_path)

    out = await cmd_workflow(workflow_context(tmp_path, "/workflow show release-check", "show release-check"))

    assert "Instruction-only workflow: release-check" in out.content
    assert "Step 1/2" in out.content
    assert "Run doctor." in out.content


@pytest.mark.asyncio
async def test_workflow_run_returns_full_checklist(tmp_path) -> None:
    write_workflow(tmp_path)

    out = await cmd_workflow(workflow_context(tmp_path, "/workflow run release-check", "run release-check"))

    assert "Step 1/2" in out.content
    assert "Step 2/2" in out.content


@pytest.mark.asyncio
async def test_workflow_step_then_next_uses_same_loop_progress(tmp_path) -> None:
    write_workflow(tmp_path)
    loop = SimpleNamespace(workspace=tmp_path)
    first = workflow_context(tmp_path, "/workflow step release-check", "step release-check")
    first.loop = loop
    second = workflow_context(tmp_path, "/workflow next", "next")
    second.loop = loop

    first_out = await cmd_workflow(first)
    second_out = await cmd_workflow(second)

    assert "Step 1/2" in first_out.content
    assert "Step 2/2" in second_out.content


@pytest.mark.asyncio
async def test_workflow_abort_after_step_returns_aborted(tmp_path) -> None:
    write_workflow(tmp_path)
    loop = SimpleNamespace(workspace=tmp_path)
    step = workflow_context(tmp_path, "/workflow step release-check", "step release-check")
    step.loop = loop
    abort = workflow_context(tmp_path, "/workflow abort", "abort")
    abort.loop = loop

    await cmd_workflow(step)
    out = await cmd_workflow(abort)

    assert "Aborted" in out.content


@pytest.mark.asyncio
async def test_workflow_next_without_active_workflow_returns_message(tmp_path) -> None:
    out = await cmd_workflow(workflow_context(tmp_path, "/workflow next", "next"))

    assert "No active workflow" in out.content


@pytest.mark.asyncio
async def test_workflow_unknown_subcommand_returns_usage(tmp_path) -> None:
    out = await cmd_workflow(workflow_context(tmp_path, "/workflow nope", "nope"))

    assert "Usage:" in out.content
