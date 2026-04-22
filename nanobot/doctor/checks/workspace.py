"""Doctor checks for the nanobot workspace directory."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from nanobot.doctor.types import DoctorCheckResult, DoctorStatus

_SECTION = "workspace"

_REQUIRED_SUBDIRS: list[tuple[str, str]] = [
    ("memory", "memory_dir"),
    ("sessions", "sessions_dir"),
    ("cron", "cron_dir"),
    ("skills", "skills_dir"),
    ("memory/skill-proposals", "skill_proposals_dir"),
]


def run_workspace_checks(workspace: Path) -> list[DoctorCheckResult]:
    """Run all workspace directory checks and return results.

    Checks performed:
    - workspace_exists: does the path exist?
    - workspace_writable: is it writable?
    - memory_dir, sessions_dir, cron_dir, skills_dir, skill_proposals_dir:
      do these runtime subdirectories exist?
    """
    results: list[DoctorCheckResult] = []

    # ── workspace_exists ──
    if not workspace.exists():
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="workspace_exists",
                status=DoctorStatus.FAIL,
                message=f"Workspace directory not found: {workspace}",
                hint="Create the workspace directory or update the config path.",
            )
        )
        return results

    results.append(
        DoctorCheckResult(
            section=_SECTION,
            check_id="workspace_exists",
            status=DoctorStatus.OK,
            message=f"Workspace directory found: {workspace}",
        )
    )

    # ── workspace_writable ──
    writable = _is_writable(workspace)
    if writable:
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="workspace_writable",
                status=DoctorStatus.OK,
                message="Workspace directory is writable.",
            )
        )
    else:
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="workspace_writable",
                status=DoctorStatus.FAIL,
                message=f"Workspace directory is not writable: {workspace}",
                hint="Check file permissions on the workspace directory.",
            )
        )
        # Skip subdir checks when workspace isn't readable/writable
        return results

    # ── runtime subdirectories ──
    for subdir_name, check_id in _REQUIRED_SUBDIRS:
        subdir_path = workspace / subdir_name
        if subdir_path.exists():
            results.append(
                DoctorCheckResult(
                    section=_SECTION,
                    check_id=check_id,
                    status=DoctorStatus.OK,
                    message=f"Directory exists: {subdir_path}",
                )
            )
        else:
            results.append(
                DoctorCheckResult(
                    section=_SECTION,
                    check_id=check_id,
                    status=DoctorStatus.WARN,
                    message=f"Directory missing: {subdir_path}",
                    hint=f"Will be created at runtime. You can create it now: mkdir -p {subdir_path}",
                )
            )

    return results


def _is_writable(path: Path) -> bool:
    """Check if a directory is writable using a lightweight probe."""
    try:
        fd, tmp = tempfile.mkstemp(dir=path, prefix=".doctor_probe_")
        os.close(fd)
        os.unlink(tmp)
        return True
    except OSError:
        return False
