from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkflowStep:
    index: int
    text: str


@dataclass(frozen=True)
class Workflow:
    name: str
    description: str
    path: Path
    fingerprint: str
    steps: list[WorkflowStep]


@dataclass(frozen=True)
class WorkflowSummary:
    name: str
    description: str
    step_count: int


@dataclass(frozen=True)
class InvalidWorkflow:
    name: str
    path: Path
    error: str


@dataclass(frozen=True)
class WorkflowList:
    workflows: list[WorkflowSummary]
    invalid: list[InvalidWorkflow]
    hint: str | None


@dataclass(frozen=True)
class WorkflowProgress:
    session_key: str
    workflow_name: str
    current_step_index: int
    total_steps: int
    path: Path
    fingerprint: str
