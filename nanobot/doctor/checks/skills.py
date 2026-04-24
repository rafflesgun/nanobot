"""Doctor checks for skill workspace readiness."""

from __future__ import annotations

from pathlib import Path

from nanobot.agent.skill_proposal_metadata import ProposalMetadataStore
from nanobot.doctor.types import DoctorCheckResult, DoctorStatus

_SECTION = "skills"


def run_skill_checks(workspace: Path) -> list[DoctorCheckResult]:
    """Validate local skill directories and cheap proposal-file issues."""
    skills_dir = workspace / "skills"
    proposals_dir = workspace / "memory" / "skill-proposals"
    results: list[DoctorCheckResult] = []

    results.append(_dir_result("skills_dir", skills_dir, "Skill install directory"))
    results.append(_dir_result("skill_proposals_dir", proposals_dir, "Skill proposal directory"))

    if proposals_dir.exists():
        malformed = []
        for path in sorted(proposals_dir.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                malformed.append(path.name)
                continue
            if not text.strip() or "description:" not in text.lower():
                malformed.append(path.name)

        if malformed:
            results.append(
                DoctorCheckResult(
                    section=_SECTION,
                    check_id="skill_proposals_format",
                    status=DoctorStatus.WARN,
                    message=f"Malformed skill proposal files detected: {', '.join(malformed)}",
                    hint="Proposal markdown should be readable and include a description field.",
                )
            )
        else:
            results.append(
                DoctorCheckResult(
                    section=_SECTION,
                    check_id="skill_proposals_format",
                    status=DoctorStatus.OK,
                    message="Skill proposal files look locally well-formed.",
                )
            )

        proposal_names = {path.stem for path in proposals_dir.glob("*.md")}
        metadata_entries = ProposalMetadataStore(workspace).list()
        drifted_names = sorted(set(metadata_entries) ^ proposal_names)

        results.extend(
            [
                _proposal_health_result(
                    check_id="skill_proposals_pending",
                    names=sorted(
                        name
                        for name in proposal_names
                        if (metadata_entries.get(name) or {}).get("status", "pending") == "pending"
                    ),
                    label="pending",
                ),
                _proposal_health_result(
                    check_id="skill_proposals_blocked",
                    names=sorted(
                        name
                        for name in proposal_names
                        if (metadata_entries.get(name) or {}).get("scan_verdict") == "block"
                    ),
                    label="blocked",
                    status=DoctorStatus.WARN,
                ),
                _proposal_health_result(
                    check_id="skill_proposals_warning",
                    names=sorted(
                        name
                        for name in proposal_names
                        if (metadata_entries.get(name) or {}).get("scan_verdict") == "warn"
                    ),
                    label="warning",
                    status=DoctorStatus.WARN,
                ),
                _proposal_health_result(
                    check_id="skill_proposals_metadata_drift",
                    names=drifted_names,
                    label="metadata drift",
                    status=DoctorStatus.WARN,
                    ok_message="Skill proposal metadata matches proposal files.",
                    warn_message="Skill proposal metadata drift detected: {names}",
                    hint="Reconcile missing proposal files or stale metadata entries under memory/skill-proposals.",
                ),
            ]
        )

    return results


def _dir_result(check_id: str, path: Path, label: str) -> DoctorCheckResult:
    if path.exists():
        return DoctorCheckResult(
            section=_SECTION,
            check_id=check_id,
            status=DoctorStatus.OK,
            message=f"{label} exists: {path}",
        )
    return DoctorCheckResult(
        section=_SECTION,
        check_id=check_id,
        status=DoctorStatus.WARN,
        message=f"{label} is missing: {path}",
        hint=f"Create it with: mkdir -p {path}",
    )


def _proposal_health_result(
    *,
    check_id: str,
    names: list[str],
    label: str,
    status: DoctorStatus = DoctorStatus.OK,
    ok_message: str | None = None,
    warn_message: str | None = None,
    hint: str | None = None,
) -> DoctorCheckResult:
    if names:
        return DoctorCheckResult(
            section=_SECTION,
            check_id=check_id,
            status=status,
            message=(warn_message or f"Skill proposals with {label} state: {{names}}.").format(
                names=", ".join(names)
            ),
            hint=hint,
        )
    return DoctorCheckResult(
        section=_SECTION,
        check_id=check_id,
        status=DoctorStatus.OK,
        message=ok_message or f"No skill proposals with {label} state.",
    )
