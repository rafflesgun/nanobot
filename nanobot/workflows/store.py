from __future__ import annotations

import re
from pathlib import Path

from nanobot.workflows.types import (
    InvalidWorkflow,
    Workflow,
    WorkflowList,
    WorkflowStep,
    WorkflowSummary,
)

VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STEP_RE = re.compile(r"^(\d+)\.\s+(.*)$")
CONTINUATION_RE = re.compile(r"^\s+(.*)$")
INVALID_NAME_ERROR = "Workflow name must be kebab-case using lowercase letters, digits, and hyphens"


class WorkflowStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.workflows_dir = workspace / "workflows"

    def list(self) -> WorkflowList:
        if not self.workflows_dir.is_dir():
            return WorkflowList(
                workflows=[],
                invalid=[],
                hint=f"Create workflow runbooks in {self.workflows_dir}",
            )

        workflows: list[WorkflowSummary] = []
        invalid: list[InvalidWorkflow] = []
        for path in sorted(self.workflows_dir.glob("*.md")):
            workflow, error = self._read_path(path.stem, path)
            if error is not None or workflow is None:
                invalid.append(InvalidWorkflow(name=path.stem, path=path, error=error or "Invalid workflow"))
                continue
            workflows.append(
                WorkflowSummary(
                    name=workflow.name,
                    description=workflow.description,
                    step_count=len(workflow.steps),
                )
            )

        return WorkflowList(workflows=workflows, invalid=invalid, hint=None)

    def read(self, name: str) -> tuple[Workflow | None, str | None]:
        if not VALID_NAME_RE.fullmatch(name):
            return None, INVALID_NAME_ERROR

        return self._read_path(name, self.workflows_dir / f"{name}.md")

    def render_full(self, workflow: Workflow) -> str:
        lines = [
            f"Instruction-only workflow: {workflow.name}",
            f"Description: {workflow.description}",
            "",
        ]
        for step in workflow.steps:
            lines.append(self.render_step(workflow, step.index))
            lines.append("")
        return "\n".join(lines).rstrip()

    def render_step(self, workflow: Workflow, step_index: int) -> str:
        step = workflow.steps[step_index - 1]
        return f"Step {step.index}/{len(workflow.steps)}\n{step.text}"

    def _read_path(self, name: str, path: Path) -> tuple[Workflow | None, str | None]:
        if not VALID_NAME_RE.fullmatch(name):
            return None, INVALID_NAME_ERROR
        if not path.is_file():
            return None, f"Workflow '{name}' not found in {self.workflows_dir}"

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            return None, f"Unable to read workflow: {exc}"

        metadata, body, error = self._parse_frontmatter(content)
        if error is not None:
            return None, error

        frontmatter_name = metadata.get("name", "")
        description = metadata.get("description", "")
        if frontmatter_name != name:
            return None, "Workflow frontmatter name must match filename"
        if not description.strip():
            return None, "Workflow description must be non-empty"

        steps = self._parse_steps(body)
        if not steps:
            return None, "Workflow must contain top-level numbered steps"

        stat = path.stat()
        workflow = Workflow(
            name=name,
            description=description,
            path=path,
            fingerprint=f"{stat.st_mtime_ns}:{stat.st_size}",
            steps=steps,
        )
        return workflow, None

    def _parse_frontmatter(self, content: str) -> tuple[dict[str, str], str, str | None]:
        lines = content.splitlines()
        if not lines or lines[0] != "---":
            return {}, "", "Workflow must start with YAML frontmatter"

        end = None
        for index, line in enumerate(lines[1:], start=1):
            if line == "---":
                end = index
                break
        if end is None:
            return {}, "", "Workflow frontmatter must be closed with ---"

        metadata: dict[str, str] = {}
        for line in lines[1:end]:
            if not line.strip():
                continue
            key, separator, value = line.partition(":")
            if not separator:
                return {}, "", "Workflow frontmatter must use key: value entries"
            metadata[key.strip()] = value.strip()

        return metadata, "\n".join(lines[end + 1 :]), None

    def _parse_steps(self, body: str) -> list[WorkflowStep]:
        steps: list[WorkflowStep] = []
        current: list[str] | None = None

        for line in body.splitlines():
            match = STEP_RE.match(line)
            if match is not None:
                if current is not None:
                    steps.append(WorkflowStep(index=len(steps) + 1, text="\n".join(current).strip()))
                current = [match.group(2).strip()]
                continue

            if current is None:
                continue

            if not line.strip():
                current.append("")
                continue

            continuation = CONTINUATION_RE.match(line)
            if continuation is not None:
                current.append(continuation.group(1).strip())

        if current is not None:
            steps.append(WorkflowStep(index=len(steps) + 1, text="\n".join(current).strip()))

        return steps
