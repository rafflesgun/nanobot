from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from nanobot.agent.loop import _LoopHook
from nanobot.agent.tools.workflow import WorkflowListTool, WorkflowRunTool
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


async def test_workflow_run_unknown_mode_returns_error(tmp_path) -> None:
    payload = json.loads(
        await WorkflowRunTool(workspace=tmp_path).execute(name="release-check", mode="invalid")
    )

    assert payload["success"] is False
    assert "mode" in payload["error"]


async def test_loop_hook_preserves_effective_session_key_before_tool_execution() -> None:
    class FakeLoop:
        def __init__(self) -> None:
            self.calls = []

        def _set_tool_context(self, channel, chat_id, message_id=None, thread_id=None, session_key=None):
            self.calls.append(
                {
                    "channel": channel,
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "thread_id": thread_id,
                    "session_key": session_key,
                }
            )

    loop = FakeLoop()
    hook = _LoopHook(
        loop,
        channel="telegram",
        chat_id="room",
        message_id="msg-1",
        thread_id=42,
        session_key="telegram:room:topic:42",
    )

    await hook.before_execute_tools(SimpleNamespace(tool_calls=[]))

    assert loop.calls == [
        {
            "channel": "telegram",
            "chat_id": "room",
            "message_id": "msg-1",
            "thread_id": 42,
            "session_key": "telegram:room:topic:42",
        }
    ]
