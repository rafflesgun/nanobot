"""Tool for safe workspace-local skill mutation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nanobot.agent.skill_proposal_metadata import ProposalMetadataStore
from nanobot.agent.skill_proposals import SkillProposalStore
from nanobot.agent.skills_manager import SkillsManager
from nanobot.agent.tools.base import Tool


class SkillManageTool(Tool):
    def __init__(self, workspace: Path, skill_usage: Any = None) -> None:
        self._manager = SkillsManager(workspace)
        self._proposals = SkillProposalStore(workspace)
        self._metadata = ProposalMetadataStore(Path(workspace))
        self._skill_usage = skill_usage

    @property
    def name(self) -> str:
        return "skill_manage"

    @property
    def description(self) -> str:
        return "Create, replace, patch, and delete workspace skills safely."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "create",
                        "replace",
                        "patch",
                        "delete",
                        "apply_proposal",
                        "reject_proposal",
                    ],
                    "description": "Skill mutation action to perform",
                },
                "name": {
                    "type": "string",
                    "description": "Target workspace skill name",
                    "minLength": 1,
                },
                "content": {
                    "type": "string",
                    "description": "Full SKILL.md content for create/replace",
                },
                "old_text": {
                    "type": "string",
                    "description": "Existing text to replace for patch",
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text for patch",
                },
            },
            "required": ["action", "name"],
        }

    async def execute(
        self,
        action: str,
        name: str | None = None,
        content: str | None = None,
        old_text: str | None = None,
        new_text: str | None = None,
        **_: Any,
    ) -> str:
        proposal_name_error = self._validate_proposal_name(name or "")
        if action == "create":
            result = self._manager.create(name or "", content or "")
        elif action == "replace":
            result = self._manager.replace(name or "", content or "")
        elif action == "patch":
            result = self._manager.patch(name or "", old_text or "", new_text or "")
        elif action == "delete":
            result = self._manager.delete(name or "")
        elif action == "apply_proposal":
            proposal_name = name or ""
            if proposal_name_error:
                result = {"success": False, "error": proposal_name_error}
                return json.dumps(result, ensure_ascii=False)
            try:
                proposal = self._proposals.read(proposal_name)
            except FileNotFoundError:
                result = {"success": False, "error": f"Proposal '{proposal_name}' does not exist"}
            else:
                result = self._manager.create(proposal_name, proposal)
                warning = self._record_apply_metadata(proposal_name, result)
                if result.get("success"):
                    self._proposals.delete(proposal_name)
                if warning:
                    result["warning"] = warning
        elif action == "reject_proposal":
            proposal_name = name or ""
            if proposal_name_error:
                result = {"success": False, "error": proposal_name_error}
                return json.dumps(result, ensure_ascii=False)
            if self._proposals.delete(proposal_name):
                result = {"success": True, "name": proposal_name}
                warning = self._record_rejected_metadata(proposal_name)
                if warning:
                    result["warning"] = warning
            else:
                result = {"success": False, "error": f"Proposal '{proposal_name}' does not exist"}
        else:
            result = {"success": False, "error": f"Unknown action: {action}"}
        return json.dumps(result, ensure_ascii=False)

    def _record_apply_metadata(self, proposal_name: str, result: dict[str, Any]) -> str | None:
        scan = result.get("scan")
        try:
            if isinstance(scan, dict):
                self._record_scan_metadata(proposal_name, scan)
            if result.get("success"):
                self._metadata.record_applied(proposal_name)
        except Exception as exc:
            return f"Skill applied, but proposal metadata update failed: {exc}"
        return None

    def _record_rejected_metadata(self, proposal_name: str) -> str | None:
        try:
            self._metadata.record_rejected(proposal_name)
        except Exception as exc:
            return f"Proposal rejected, but metadata update failed: {exc}"
        return None

    def _record_scan_metadata(self, proposal_name: str, scan: dict[str, Any]) -> None:
        verdict = str(scan.get("verdict") or "unknown")
        summary = str(scan.get("summary") or "")
        self._metadata.record_scan(proposal_name, verdict=verdict, summary=summary)

    @staticmethod
    def _validate_proposal_name(name: str) -> str | None:
        if (
            not name
            or any(sep in name for sep in ("/", "\\"))
            or name.startswith(".")
            or ".." in name
        ):
            return "Proposal name must be a simple skill identifier"
        return None
