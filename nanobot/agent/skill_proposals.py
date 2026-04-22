"""Storage helpers for Dream-generated skill proposals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class SkillProposal:
    name: str
    path: Path
    description: str | None


class SkillProposalStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.dir = workspace / "memory" / "skill-proposals"
        self.dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, name: str) -> Path:
        return self.dir / f"{name}.md"

    def write(self, name: str, content: str) -> Path:
        path = self.path_for(name)
        path.write_text(content, encoding="utf-8")
        return path

    def read(self, name: str) -> str:
        return self.path_for(name).read_text(encoding="utf-8")

    def list(self) -> list[SkillProposal]:
        proposals: list[SkillProposal] = []
        for path in sorted(self.dir.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            match = re.search(r"^description:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
            proposals.append(
                SkillProposal(
                    name=path.stem,
                    path=path,
                    description=match.group(1).strip() if match else None,
                )
            )
        return proposals

    def delete(self, name: str) -> bool:
        path = self.path_for(name)
        if not path.exists():
            return False
        path.unlink()
        return True
