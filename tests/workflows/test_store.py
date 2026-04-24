from __future__ import annotations

from pathlib import Path

from nanobot.workflows.store import WorkflowStore


def write_workflow(workspace: Path, name: str, content: str) -> Path:
    workflows_dir = workspace / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    path = workflows_dir / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_list_returns_empty_with_hint_when_directory_missing(tmp_path) -> None:
    result = WorkflowStore(tmp_path).list()

    assert result.workflows == []
    assert result.invalid == []
    assert "workflows" in result.hint


def test_list_parses_valid_workflow_summary(tmp_path) -> None:
    write_workflow(
        tmp_path,
        "release-check",
        """---
name: release-check
description: Pre-release validation checklist
---

# Release Check

1. Run doctor and inspect failures.
2. Run focused tests.
""",
    )

    result = WorkflowStore(tmp_path).list()

    assert result.hint is None
    assert result.invalid == []
    assert len(result.workflows) == 1
    summary = result.workflows[0]
    assert summary.name == "release-check"
    assert summary.description == "Pre-release validation checklist"
    assert summary.step_count == 2


def test_list_parses_yaml_frontmatter_syntax(tmp_path) -> None:
    write_workflow(
        tmp_path,
        "release-check",
        """---
# Comments are valid YAML frontmatter.
name: release-check
description: "Pre-release: validation checklist"
---

1. Run doctor.
""",
    )

    result = WorkflowStore(tmp_path).list()

    assert result.invalid == []
    assert len(result.workflows) == 1
    assert result.workflows[0].description == "Pre-release: validation checklist"


def test_read_rejects_frontmatter_name_mismatch(tmp_path) -> None:
    write_workflow(
        tmp_path,
        "release-check",
        """---
name: wrong-name
description: Pre-release validation checklist
---

1. Run doctor.
""",
    )

    result = WorkflowStore(tmp_path).list()

    assert result.workflows == []
    assert len(result.invalid) == 1
    assert result.invalid[0].name == "release-check"
    assert "must match" in result.invalid[0].error


def test_read_rejects_invalid_yaml_frontmatter(tmp_path) -> None:
    write_workflow(
        tmp_path,
        "release-check",
        """---
name: [release-check
description: Pre-release validation checklist
---

1. Run doctor.
""",
    )

    workflow, error = WorkflowStore(tmp_path).read("release-check")

    assert workflow is None
    assert error is not None
    assert "Invalid YAML frontmatter" in error


def test_read_rejects_non_mapping_frontmatter(tmp_path) -> None:
    write_workflow(
        tmp_path,
        "release-check",
        """---
- release-check
---

1. Run doctor.
""",
    )

    workflow, error = WorkflowStore(tmp_path).read("release-check")

    assert workflow is None
    assert error == "Workflow frontmatter must parse to a mapping"


def test_read_rejects_non_string_description(tmp_path) -> None:
    write_workflow(
        tmp_path,
        "release-check",
        """---
name: release-check
description: 123
---

1. Run doctor.
""",
    )

    workflow, error = WorkflowStore(tmp_path).read("release-check")

    assert workflow is None
    assert error is not None
    assert "description" in error


def test_read_rejects_missing_numbered_steps(tmp_path) -> None:
    write_workflow(
        tmp_path,
        "release-check",
        """---
name: release-check
description: Pre-release validation checklist
---

## Step One

Run doctor.
""",
    )

    workflow, error = WorkflowStore(tmp_path).read("release-check")

    assert workflow is None
    assert error is not None
    assert "numbered" in error


def test_parses_numbered_steps_with_continuation_lines(tmp_path) -> None:
    write_workflow(
        tmp_path,
        "release-check",
        """---
name: release-check
description: Pre-release validation checklist
---

1. Run doctor.
   Inspect failures before continuing.
2. Summarize risks.
""",
    )

    workflow, error = WorkflowStore(tmp_path).read("release-check")

    assert error is None
    assert workflow is not None
    assert workflow.steps[0].text == "Run doctor.\nInspect failures before continuing."
    assert workflow.steps[1].text == "Summarize risks."


def test_read_rejects_unsafe_name(tmp_path) -> None:
    workflow, error = WorkflowStore(tmp_path).read("../secret")

    assert workflow is None
    assert error == "Workflow name must be kebab-case using lowercase letters, digits, and hyphens"


def test_render_full_workflow_is_instructional(tmp_path) -> None:
    write_workflow(
        tmp_path,
        "release-check",
        """---
name: release-check
description: Pre-release validation checklist
---

1. Run doctor.
2. Summarize risks.
""",
    )

    workflow, error = WorkflowStore(tmp_path).read("release-check")

    assert error is None
    assert workflow is not None
    rendered = WorkflowStore(tmp_path).render_full(workflow)

    assert "Instruction-only workflow" in rendered
    assert "1/2" in rendered
    assert "Run doctor." in rendered
