"""Safe workspace-local skill mutation utilities."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

from nanobot.skills.scan import scan_skill_content


class SkillsManager:
    VALID_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.skills_dir = workspace / "skills"

    def create(self, name: str, content: str) -> dict[str, Any]:
        error = self._validate_target(name)
        if error:
            return {"success": False, "error": error}
        meta, error = self._validate_content(name, content)
        if error:
            return {"success": False, "error": error}
        scan = self._scan_content(name, content)
        if scan["verdict"] == "block":
            return {
                "success": False,
                "error": "Skill content blocked by safety scan",
                "scan": scan,
            }
        path = self._skill_path(name)
        if path.exists():
            return {"success": False, "error": f"Skill '{name}' already exists"}
        self._atomic_write(path, content)
        return {
            "success": True,
            "name": name,
            "path": str(path),
            "description": meta["description"],
            "scan": scan,
        }

    def replace(self, name: str, content: str) -> dict[str, Any]:
        error = self._validate_target(name)
        if error:
            return {"success": False, "error": error}
        meta, error = self._validate_content(name, content)
        if error:
            return {"success": False, "error": error}
        scan = self._scan_content(name, content)
        if scan["verdict"] == "block":
            return {
                "success": False,
                "error": "Skill content blocked by safety scan",
                "scan": scan,
            }
        path = self._skill_path(name)
        if not path.exists():
            return {"success": False, "error": f"Skill '{name}' does not exist"}
        self._atomic_write(path, content)
        return {
            "success": True,
            "name": name,
            "path": str(path),
            "description": meta["description"],
            "scan": scan,
        }

    def patch(self, name: str, old_text: str, new_text: str) -> dict[str, Any]:
        error = self._validate_target(name)
        if error:
            return {"success": False, "error": error}
        path = self._skill_path(name)
        if not path.exists():
            return {"success": False, "error": f"Skill '{name}' does not exist"}
        current = path.read_text(encoding="utf-8")
        if old_text not in current:
            return {"success": False, "error": "old_text not found in skill content"}
        updated = current.replace(old_text, new_text, 1)
        _, validate_error = self._validate_content(name, updated)
        if validate_error:
            return {"success": False, "error": validate_error}
        scan = self._scan_content(name, updated)
        if scan["verdict"] == "block":
            return {
                "success": False,
                "error": "Skill content blocked by safety scan",
                "scan": scan,
            }
        self._atomic_write(path, updated)
        return {"success": True, "name": name, "path": str(path), "scan": scan}

    def delete(self, name: str) -> dict[str, Any]:
        error = self._validate_target(name)
        if error:
            return {"success": False, "error": error}
        skill_dir = self.skills_dir / name
        path = self._skill_path(name)
        if not path.exists():
            return {"success": False, "error": f"Skill '{name}' does not exist"}
        path.unlink()
        try:
            skill_dir.rmdir()
        except OSError:
            pass
        return {"success": True, "name": name}

    def _validate_target(self, name: str) -> str | None:
        if not name or not self.VALID_NAME_RE.fullmatch(name):
            return "Skill name must be kebab-case using lowercase letters, digits, and hyphens"
        return None

    def _validate_content(
        self, expected_name: str, content: str
    ) -> tuple[dict[str, Any], str | None]:
        if not content.startswith("---"):
            return {}, "Skill content must include YAML frontmatter"

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, "Skill content must include closing YAML frontmatter delimiter"

        try:
            meta = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError as exc:
            return {}, f"Invalid YAML frontmatter: {exc}"
        if not isinstance(meta, dict):
            return {}, "Skill frontmatter must parse to a mapping"

        name = meta.get("name")
        description = meta.get("description")
        if not isinstance(name, str) or not name.strip():
            return {}, "Skill frontmatter must include a non-empty name"
        if name != expected_name:
            return {}, f"Skill frontmatter name '{name}' must match target '{expected_name}'"
        if not isinstance(description, str) or not description.strip():
            return {}, "Skill frontmatter must include a non-empty description"

        return {"name": name, "description": description}, None

    def _skill_path(self, name: str) -> Path:
        return self.skills_dir / name / "SKILL.md"

    @staticmethod
    def _scan_content(name: str, content: str) -> dict[str, Any]:
        return scan_skill_content(name, content).model_dump()

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", delete=False, dir=path.parent
        ) as handle:
            handle.write(content)
            temp_name = handle.name
        os.replace(temp_name, path)
