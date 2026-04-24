"""Storage helpers for Dream-generated skill proposals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from nanobot.agent.skill_proposal_metadata import ProposalMetadataStore


@dataclass(slots=True)
class SkillProposal:
    name: str
    path: Path
    description: str | None
    source: str | None
    status: str | None
    last_scan_verdict: str | None


class SkillProposalStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.dir = workspace / "memory" / "skill-proposals"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.metadata = ProposalMetadataStore(workspace)

    def path_for(self, name: str) -> Path:
        return self.dir / f"{name}.md"

    def write(self, name: str, content: str, source: str = "dream") -> Path:
        path = self.path_for(name)
        path.write_text(content, encoding="utf-8")
        self.metadata.record_created(name=name, source=source)
        return path

    def read(self, name: str) -> str:
        return self.path_for(name).read_text(encoding="utf-8")

    def list(self) -> list[SkillProposal]:
        proposals: list[SkillProposal] = []
        for path in sorted(self.dir.glob("*.md")):
            content = path.read_text(encoding="utf-8")
            match = re.search(r"^description:\s*(.+)$", content, re.MULTILINE | re.IGNORECASE)
            metadata = self.metadata.get(path.stem) or {}
            proposals.append(
                SkillProposal(
                    name=path.stem,
                    path=path,
                    description=match.group(1).strip() if match else None,
                    source=metadata.get("source"),
                    status=metadata.get("status"),
                    last_scan_verdict=metadata.get("scan_verdict"),
                )
            )
        return proposals

    def delete(self, name: str) -> bool:
        path = self.path_for(name)
        if not path.exists():
            return False
        path.unlink()
        return True
