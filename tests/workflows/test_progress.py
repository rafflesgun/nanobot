from __future__ import annotations

from pathlib import Path

from nanobot.workflows.progress import WorkflowProgressManager
from nanobot.workflows.store import WorkflowStore


def write_workflow(workspace: Path, body: str = "1. First step.\n2. Second step.\n") -> None:
    workflows_dir = workspace / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "release-check.md").write_text(
        f"""---
name: release-check
description: Pre-release validation checklist
---

{body}""",
        encoding="utf-8",
    )


def test_start_returns_first_step(tmp_path) -> None:
    write_workflow(tmp_path)
    manager = WorkflowProgressManager(WorkflowStore(tmp_path))

    result = manager.start("cli:direct", "release-check")

    assert result.success is True
    assert result.completed is False
    assert "Step 1/2" in result.output
    assert "First step." in result.output


def test_next_advances_and_completes(tmp_path) -> None:
    write_workflow(tmp_path)
    manager = WorkflowProgressManager(WorkflowStore(tmp_path))
    manager.start("cli:direct", "release-check")

    second = manager.next("cli:direct")
    done = manager.next("cli:direct")

    assert second.success is True
    assert "Step 2/2" in second.output
    assert "Second step." in second.output
    assert done.success is True
    assert done.completed is True
    assert "complete" in done.output.lower()


def test_next_without_active_workflow_returns_error(tmp_path) -> None:
    manager = WorkflowProgressManager(WorkflowStore(tmp_path))

    result = manager.next("cli:direct")

    assert result.success is False
    assert "No active workflow" in result.output


def test_abort_clears_active_workflow(tmp_path) -> None:
    write_workflow(tmp_path)
    manager = WorkflowProgressManager(WorkflowStore(tmp_path))
    manager.start("cli:direct", "release-check")

    aborted = manager.abort("cli:direct")
    next_result = manager.next("cli:direct")

    assert aborted.success is True
    assert "Aborted" in aborted.output
    assert next_result.success is False


def test_file_change_requires_restart(tmp_path) -> None:
    write_workflow(tmp_path)
    manager = WorkflowProgressManager(WorkflowStore(tmp_path))
    manager.start("cli:direct", "release-check")
    write_workflow(tmp_path, body="1. Changed step.\n")

    result = manager.next("cli:direct")

    assert result.success is False
    assert "restart" in result.output.lower()
