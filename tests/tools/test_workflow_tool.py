from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from nanobot.agent.tools.workflow import WorkflowListTool, WorkflowRunTool
from nanobot.bus.queue import MessageBus
from nanobot.workflows.progress import WorkflowProgressManager
from nanobot.workflows.store import WorkflowStore


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


def write_other_workflow(workspace: Path) -> None:
    workflows_dir = workspace / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    (workflows_dir / "deploy-check.md").write_text(
        """---
name: deploy-check
description: Deployment validation checklist
---

1. Check deploy target.
2. Confirm health checks.
""",
        encoding="utf-8",
    )


async def test_workflow_list_returns_summaries_and_invalid_entries(tmp_path) -> None:
    write_workflow(tmp_path)
    (tmp_path / "workflows" / "broken.md").write_text("not frontmatter", encoding="utf-8")

    payload = json.loads(await WorkflowListTool(workspace=tmp_path).execute())

    assert payload["success"] is True
    assert payload["hint"] is None
    assert payload["workflows"] == [
        {
            "name": "release-check",
            "description": "Pre-release validation checklist",
            "step_count": 2,
        }
    ]
    assert len(payload["invalid"]) == 1
    assert payload["invalid"][0]["name"] == "broken"
    assert isinstance(payload["invalid"][0]["path"], str)


async def test_workflow_list_returns_empty_when_no_workflows_exist(tmp_path) -> None:
    payload = json.loads(await WorkflowListTool(workspace=tmp_path).execute())

    assert payload["success"] is True
    assert payload["workflows"] == []
    assert payload["invalid"] == []


async def test_workflow_run_full_returns_instruction_text(tmp_path) -> None:
    write_workflow(tmp_path)

    payload = json.loads(
        await WorkflowRunTool(workspace=tmp_path).execute(name="release-check", mode="full")
    )

    assert payload["success"] is True
    assert payload["name"] == "release-check"
    assert payload["mode"] == "full"
    assert "Instruction-only workflow" in payload["output"]
    assert "Run doctor." in payload["output"]


async def test_workflow_run_step_uses_session_context(tmp_path) -> None:
    write_workflow(tmp_path)
    store = WorkflowStore(tmp_path)
    progress = WorkflowProgressManager(store)
    tool = WorkflowRunTool(workspace=tmp_path, store=store, progress=progress)
    tool.set_context(session_key="cli:direct")

    first = json.loads(await tool.execute(name="release-check", mode="step"))
    second = json.loads(await tool.execute(name="release-check", mode="step"))

    assert first["success"] is True
    assert first["mode"] == "step"
    assert "Step 1/2" in first["output"]
    assert second["success"] is True
    assert "Step 2/2" in second["output"]


async def test_workflow_run_step_does_not_restart_after_completion(tmp_path) -> None:
    write_workflow(tmp_path)
    tool = WorkflowRunTool(workspace=tmp_path)
    tool.set_context(session_key="cli:direct")

    await tool.execute(name="release-check", mode="step")
    await tool.execute(name="release-check", mode="step")
    completed = json.loads(await tool.execute(name="release-check", mode="step"))
    after_completed = json.loads(await tool.execute(name="release-check", mode="step"))

    assert completed["success"] is True
    assert "complete" in completed["output"].lower()
    assert after_completed["success"] is True
    assert "complete" in after_completed["output"].lower()
    assert "Step 1/2" not in after_completed["output"]


async def test_workflow_run_step_rejects_different_active_workflow(tmp_path) -> None:
    write_workflow(tmp_path)
    write_other_workflow(tmp_path)
    tool = WorkflowRunTool(workspace=tmp_path)
    tool.set_context(session_key="cli:direct")

    first = json.loads(await tool.execute(name="release-check", mode="step"))
    mismatch = json.loads(await tool.execute(name="deploy-check", mode="step"))

    assert "Step 1/2" in first["output"]
    assert mismatch["success"] is False
    assert "release-check" in mismatch["error"]
    assert "abort" in mismatch["error"].lower() or "active" in mismatch["error"].lower()
    assert "Confirm health checks" not in mismatch["output"]


async def test_workflow_run_step_clears_stale_active_workflow_before_switch(tmp_path) -> None:
    write_workflow(tmp_path)
    write_other_workflow(tmp_path)
    tool = WorkflowRunTool(workspace=tmp_path)
    tool.set_context(session_key="cli:direct")

    first = json.loads(await tool.execute(name="release-check", mode="step"))
    (tmp_path / "workflows" / "release-check.md").unlink()
    stale = json.loads(await tool.execute(name="deploy-check", mode="step"))
    switched = json.loads(await tool.execute(name="deploy-check", mode="step"))

    assert "Step 1/2" in first["output"]
    assert stale["success"] is False
    assert "release-check" in stale["error"]
    assert "restart" in stale["error"].lower() or "readable" in stale["error"].lower()
    assert switched["success"] is True
    assert switched["name"] == "deploy-check"
    assert "Step 1/2" in switched["output"]
    assert "Check deploy target." in switched["output"]


async def test_workflow_run_step_reports_changed_active_workflow_without_restart(tmp_path) -> None:
    write_workflow(tmp_path)
    tool = WorkflowRunTool(workspace=tmp_path)
    tool.set_context(session_key="cli:direct")

    first = json.loads(await tool.execute(name="release-check", mode="step"))
    write_workflow(tmp_path)
    stale = json.loads(await tool.execute(name="release-check", mode="step"))
    restarted = json.loads(await tool.execute(name="release-check", mode="step"))

    assert "Step 1/2" in first["output"]
    assert stale["success"] is False
    assert stale["name"] == "release-check"
    assert "changed" in stale["error"].lower() or "restart" in stale["error"].lower()
    assert "Step 1/2" not in stale["output"]
    assert restarted["success"] is True
    assert "Step 1/2" in restarted["output"]


async def test_workflow_run_step_is_isolated_by_session_key(tmp_path) -> None:
    write_workflow(tmp_path)
    store = WorkflowStore(tmp_path)
    progress = WorkflowProgressManager(store)
    tool = WorkflowRunTool(workspace=tmp_path, store=store, progress=progress)

    tool.set_context(session_key="cli:first")
    first_session = json.loads(await tool.execute(name="release-check", mode="step"))
    tool.set_context(session_key="cli:second")
    second_session = json.loads(await tool.execute(name="release-check", mode="step"))

    assert first_session["success"] is True
    assert "Step 1/2" in first_session["output"]
    assert second_session["success"] is True
    assert "Step 1/2" in second_session["output"]


async def test_workflow_run_keeps_task_local_session_context(tmp_path) -> None:
    write_workflow(tmp_path)
    store = WorkflowStore(tmp_path)
    progress = WorkflowProgressManager(store)
    tool = WorkflowRunTool(workspace=tmp_path, store=store, progress=progress)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def task_one() -> tuple[dict, dict]:
        tool.set_context(session_key="session-one")
        first = json.loads(await tool.execute(name="release-check", mode="step"))
        entered.set()
        await release.wait()
        second = json.loads(await tool.execute(name="release-check", mode="step"))
        return first, second

    async def task_two() -> dict:
        await entered.wait()
        tool.set_context(session_key="session-two")
        first = json.loads(await tool.execute(name="release-check", mode="step"))
        release.set()
        return first

    (task_one_first, task_one_second), task_two_first = await asyncio.gather(task_one(), task_two())

    assert task_one_first["success"] is True
    assert "Step 1/2" in task_one_first["output"]
    assert task_one_second["success"] is True
    assert "Step 2/2" in task_one_second["output"]
    assert task_two_first["success"] is True
    assert "Step 1/2" in task_two_first["output"]
    assert progress.active("session-one").current_step_index == 2
    assert progress.active("session-two").current_step_index == 1


async def test_workflow_tool_concurrency_contract(tmp_path) -> None:
    run_tool = WorkflowRunTool(workspace=tmp_path)
    list_tool = WorkflowListTool(workspace=tmp_path)

    assert run_tool.read_only is True
    assert run_tool.exclusive is True
    assert run_tool.concurrency_safe is False
    assert list_tool.read_only is True
    assert list_tool.exclusive is False
    assert list_tool.concurrency_safe is True


def test_agent_loop_registers_workflow_run_with_shared_progress(tmp_path) -> None:
    from nanobot.agent.loop import AgentLoop

    provider = SimpleNamespace(
        get_default_model=lambda: "test-model",
        generation=SimpleNamespace(max_tokens=4096),
    )

    loop = AgentLoop(bus=MessageBus(), provider=provider, workspace=tmp_path, model="test-model")
    tool = loop.tools.get("workflow_run")

    assert isinstance(tool, WorkflowRunTool)


async def test_workflow_run_unknown_mode_returns_error(tmp_path) -> None:
    payload = json.loads(
        await WorkflowRunTool(workspace=tmp_path).execute(name="release-check", mode="invalid")
    )

    assert payload["success"] is False
    assert "mode" in payload["error"]


async def test_loop_hook_preserves_effective_session_key_before_tool_execution() -> None:
    from nanobot.agent.progress_hook import AgentProgressHook

    hook = AgentProgressHook(
        channel="telegram",
        chat_id="room",
        message_id="msg-1",
        session_key="telegram:room:topic:42",
    )

    assert hook._session_key == "telegram:room:topic:42"
    assert hook._channel == "telegram"
    assert hook._chat_id == "room"
    assert hook._message_id == "msg-1"
