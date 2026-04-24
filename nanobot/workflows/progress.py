from __future__ import annotations

from nanobot.workflows.store import WorkflowStore
from nanobot.workflows.types import WorkflowProgress, WorkflowProgressResult


class WorkflowProgressManager:
    def __init__(self, store: WorkflowStore) -> None:
        self.store = store
        self._progress: dict[str, WorkflowProgress] = {}

    def start(self, session_key: str, name: str) -> WorkflowProgressResult:
        workflow, error = self.store.read(name)
        if error is not None or workflow is None:
            self._progress.pop(session_key, None)
            return WorkflowProgressResult(success=False, output=error or "Unable to read workflow", workflow_name=name)

        progress = WorkflowProgress(
            session_key=session_key,
            workflow_name=workflow.name,
            current_step_index=1,
            total_steps=len(workflow.steps),
            path=workflow.path,
            fingerprint=workflow.fingerprint,
        )
        self._progress[session_key] = progress
        return WorkflowProgressResult(
            success=True,
            output=self.store.render_step(workflow, progress.current_step_index),
            workflow_name=workflow.name,
            current_step_index=progress.current_step_index,
            total_steps=progress.total_steps,
        )

    def active(self, session_key: str) -> WorkflowProgress | None:
        return self._progress.get(session_key)

    def validate(self, session_key: str) -> WorkflowProgressResult | None:
        progress = self._progress.get(session_key)
        if progress is None:
            return None

        workflow, error = self.store.read(progress.workflow_name)
        if error is not None or workflow is None:
            self._progress.pop(session_key, None)
            return WorkflowProgressResult(
                success=False,
                output=f"Workflow '{progress.workflow_name}' is no longer readable. Please restart the workflow.",
                workflow_name=progress.workflow_name,
            )

        if workflow.fingerprint != progress.fingerprint:
            self._progress.pop(session_key, None)
            return WorkflowProgressResult(
                success=False,
                output=f"Workflow '{progress.workflow_name}' changed. Please restart the workflow.",
                workflow_name=progress.workflow_name,
            )

        return None

    def next(self, session_key: str) -> WorkflowProgressResult:
        progress = self._progress.get(session_key)
        if progress is None:
            return WorkflowProgressResult(success=False, output="No active workflow. Start a workflow first.")

        workflow, error = self.store.read(progress.workflow_name)
        if error is not None or workflow is None:
            self._progress.pop(session_key, None)
            return WorkflowProgressResult(
                success=False,
                output=f"Workflow '{progress.workflow_name}' is no longer readable. Please restart the workflow.",
                workflow_name=progress.workflow_name,
            )

        if workflow.fingerprint != progress.fingerprint:
            self._progress.pop(session_key, None)
            return WorkflowProgressResult(
                success=False,
                output=f"Workflow '{progress.workflow_name}' changed. Please restart the workflow.",
                workflow_name=progress.workflow_name,
            )

        next_step_index = progress.current_step_index + 1
        if next_step_index > progress.total_steps:
            self._progress.pop(session_key, None)
            return WorkflowProgressResult(
                success=True,
                output=f"Workflow '{progress.workflow_name}' complete.",
                workflow_name=progress.workflow_name,
                total_steps=progress.total_steps,
                completed=True,
            )

        next_progress = WorkflowProgress(
            session_key=session_key,
            workflow_name=progress.workflow_name,
            current_step_index=next_step_index,
            total_steps=progress.total_steps,
            path=progress.path,
            fingerprint=progress.fingerprint,
        )
        self._progress[session_key] = next_progress
        return WorkflowProgressResult(
            success=True,
            output=self.store.render_step(workflow, next_step_index),
            workflow_name=progress.workflow_name,
            current_step_index=next_step_index,
            total_steps=progress.total_steps,
        )

    def abort(self, session_key: str) -> WorkflowProgressResult:
        progress = self._progress.pop(session_key, None)
        if progress is None:
            return WorkflowProgressResult(success=False, output="No active workflow to abort.")

        return WorkflowProgressResult(
            success=True,
            output=f"Aborted workflow '{progress.workflow_name}'.",
            workflow_name=progress.workflow_name,
        )
