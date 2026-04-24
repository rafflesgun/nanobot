from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.workflows.progress import WorkflowProgressManager
from nanobot.workflows.store import WorkflowStore


class WorkflowListTool(Tool):
    def __init__(self, workspace: Path) -> None:
        self._store = WorkflowStore(Path(workspace))

    @property
    def name(self) -> str:
        return "workflow_list"

    @property
    def description(self) -> str:
        return "List instruction-only workflows; this tool does not execute commands."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **_: Any) -> str:
        result = self._store.list()
        payload = {
            "success": True,
            "hint": result.hint,
            "workflows": [
                {
                    "name": workflow.name,
                    "description": workflow.description,
                    "step_count": workflow.step_count,
                }
                for workflow in result.workflows
            ],
            "invalid": [
                {
                    "name": invalid.name,
                    "path": str(invalid.path),
                    "error": invalid.error,
                }
                for invalid in result.invalid
            ],
        }
        return json.dumps(payload, ensure_ascii=False)


class WorkflowRunTool(Tool):
    def __init__(
        self,
        workspace: Path,
        store: WorkflowStore | None = None,
        progress: WorkflowProgressManager | None = None,
    ) -> None:
        self._store = store or WorkflowStore(Path(workspace))
        self._progress = progress or WorkflowProgressManager(self._store)
        self._session_key = "cli:direct"
        self._completed: dict[str, str] = {}

    def set_context(self, session_key: str | None = None, **_: Any) -> None:
        if session_key:
            self._session_key = session_key

    @property
    def name(self) -> str:
        return "workflow_run"

    @property
    def description(self) -> str:
        return "Return workflow instructions and never execute commands or tools."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Workflow name to read",
                    "minLength": 1,
                },
                "mode": {
                    "type": "string",
                    "description": "Return the full workflow or the next session step",
                    "enum": ["full", "step"],
                    "default": "full",
                },
            },
            "required": ["name"],
        }

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, name: str, mode: str = "full", **_: Any) -> str:
        if mode == "full":
            return self._execute_full(name)
        if mode == "step":
            return self._execute_step(name)
        return json.dumps({"success": False, "error": f"Unknown mode: {mode}"}, ensure_ascii=False)

    def _execute_full(self, name: str) -> str:
        workflow, error = self._store.read(name)
        if error is not None or workflow is None:
            return json.dumps({"success": False, "error": error or "Unable to read workflow"}, ensure_ascii=False)
        return json.dumps(
            {
                "success": True,
                "name": workflow.name,
                "mode": "full",
                "output": self._store.render_full(workflow),
            },
            ensure_ascii=False,
        )

    def _execute_step(self, name: str) -> str:
        if self._completed.get(self._session_key) == name:
            return json.dumps(
                {
                    "success": True,
                    "name": name,
                    "mode": "step",
                    "output": f"Workflow '{name}' complete.",
                },
                ensure_ascii=False,
            )

        stale = self._progress.validate(self._session_key)
        if stale is not None:
            return self._step_payload(stale, name=name)

        active = self._progress.active(self._session_key)
        if active is not None and active.workflow_name != name:
            output = (
                f"Workflow '{active.workflow_name}' is active. "
                f"Complete or abort it before starting '{name}'."
            )
            return json.dumps(
                {
                    "success": False,
                    "name": name,
                    "mode": "step",
                    "output": output,
                    "error": output,
                },
                ensure_ascii=False,
            )

        progress = self._progress.next(self._session_key)
        if not progress.success and "No active workflow" in progress.output:
            self._completed.pop(self._session_key, None)
            progress = self._progress.start(self._session_key, name)
        elif progress.completed:
            self._completed[self._session_key] = progress.workflow_name or name
        return self._step_payload(progress, name=name)

    def _step_payload(self, progress, name: str) -> str:
        payload = {
            "success": progress.success,
            "name": progress.workflow_name or name,
            "mode": "step",
            "output": progress.output,
        }
        if not progress.success:
            payload["error"] = progress.output
        return json.dumps(payload, ensure_ascii=False)
