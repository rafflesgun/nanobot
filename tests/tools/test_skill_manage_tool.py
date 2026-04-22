from __future__ import annotations

import json

import pytest

from nanobot.agent.tools.skill_manage import SkillManageTool


@pytest.mark.asyncio
async def test_skill_manage_create_returns_json_result(tmp_path) -> None:
    tool = SkillManageTool(tmp_path)

    raw = await tool.execute(
        action="create",
        name="deploy-check",
        content="---\nname: deploy-check\ndescription: Check deploy state\n---\n\n# Deploy Check\n",
    )

    data = json.loads(raw)
    assert data["success"] is True


@pytest.mark.asyncio
async def test_skill_manage_rejects_unknown_action(tmp_path) -> None:
    tool = SkillManageTool(tmp_path)

    raw = await tool.execute(action="explode", name="deploy-check")

    data = json.loads(raw)
    assert data["success"] is False


@pytest.mark.asyncio
async def test_skill_manage_apply_proposal_installs_skill_and_removes_proposal(tmp_path) -> None:
    proposal_dir = tmp_path / "memory" / "skill-proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    (proposal_dir / "deploy-check.md").write_text(
        "---\nname: deploy-check\ndescription: Check deploy state\n---\n\n# Deploy Check\n",
        encoding="utf-8",
    )

    tool = SkillManageTool(tmp_path)

    raw = await tool.execute(action="apply_proposal", name="deploy-check")

    data = json.loads(raw)
    assert data["success"] is True
    assert (tmp_path / "skills" / "deploy-check" / "SKILL.md").exists()
    assert not (proposal_dir / "deploy-check.md").exists()


@pytest.mark.asyncio
async def test_skill_manage_reject_proposal_removes_file(tmp_path) -> None:
    proposal_dir = tmp_path / "memory" / "skill-proposals"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    (proposal_dir / "deploy-check.md").write_text(
        "---\nname: deploy-check\ndescription: Check deploy state\n---\n\n# Deploy Check\n",
        encoding="utf-8",
    )

    tool = SkillManageTool(tmp_path)

    raw = await tool.execute(action="reject_proposal", name="deploy-check")

    data = json.loads(raw)
    assert data["success"] is True
    assert not (proposal_dir / "deploy-check.md").exists()


@pytest.mark.asyncio
async def test_skill_manage_reject_proposal_rejects_path_traversal(tmp_path) -> None:
    memory_file = tmp_path / "memory" / "MEMORY.md"
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    memory_file.write_text("keep me\n", encoding="utf-8")

    tool = SkillManageTool(tmp_path)

    raw = await tool.execute(action="reject_proposal", name="../MEMORY")

    data = json.loads(raw)
    assert data["success"] is False
    assert memory_file.read_text(encoding="utf-8") == "keep me\n"


@pytest.mark.asyncio
async def test_skill_manage_apply_proposal_rejects_path_traversal(tmp_path) -> None:
    note = tmp_path / "memory" / "notes.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("secret\n", encoding="utf-8")

    tool = SkillManageTool(tmp_path)

    raw = await tool.execute(action="apply_proposal", name="../notes")

    data = json.loads(raw)
    assert data["success"] is False
    assert note.read_text(encoding="utf-8") == "secret\n"
