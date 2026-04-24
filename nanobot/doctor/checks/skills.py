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
        metadata_store = ProposalMetadataStore(workspace)
        metadata_entries = metadata_store.list()
        metadata_path = metadata_store.path

        metadata_warning: DoctorCheckResult | None = None
        if metadata_path.exists() and not metadata_entries:
            metadata_warning = DoctorCheckResult(
                section=_SECTION,
                check_id="skill_proposals_metadata_drift",
                status=DoctorStatus.WARN,
                message=f"Skill proposal metadata is unreadable or malformed: {metadata_path}",
                hint="Repair or recreate memory/skill-proposals/.metadata.json.",
            )

        drifted_names: list[str] = []
        for name in sorted(metadata_entries):
            entry = metadata_entries.get(name) or {}
            status = entry.get("status", "pending")
            has_file = name in proposal_names
            if status == "pending" and not has_file:
                drifted_names.append(name)
            elif status in {"applied", "rejected"} and has_file:
                drifted_names.append(name)

        for name in sorted(proposal_names):
            if name not in metadata_entries:
                drifted_names.append(name)

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
            ]
        )

        if metadata_warning is not None:
            results.append(metadata_warning)
        else:
            results.append(
                _proposal_health_result(
                    check_id="skill_proposals_metadata_drift",
                    names=drifted_names,
                    label="metadata drift",
                    status=DoctorStatus.WARN,
                    ok_message="Skill proposal metadata matches proposal files.",
                    warn_message="Skill proposal metadata drift detected: {names}",
                    hint="Reconcile pending proposals missing files, or applied/rejected proposals still present on disk.",
                )
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
