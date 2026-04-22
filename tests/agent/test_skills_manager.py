from __future__ import annotations

from pathlib import Path

from nanobot.agent.skills_manager import SkillsManager


def test_create_skill_requires_frontmatter(tmp_path: Path) -> None:
    manager = SkillsManager(tmp_path)

    result = manager.create("bad-skill", "# Missing frontmatter")

    assert result["success"] is False
    assert "frontmatter" in result["error"].lower()


def test_create_skill_writes_workspace_skill(tmp_path: Path) -> None:
    manager = SkillsManager(tmp_path)
    content = "---\nname: deploy-check\ndescription: Check deploy state\n---\n\n# Deploy Check\n"

    result = manager.create("deploy-check", content)

    assert result["success"] is True
    assert (tmp_path / "skills" / "deploy-check" / "SKILL.md").exists()


def test_delete_skill_refuses_missing_target(tmp_path: Path) -> None:
    manager = SkillsManager(tmp_path)

    result = manager.delete("missing-skill")

    assert result["success"] is False
