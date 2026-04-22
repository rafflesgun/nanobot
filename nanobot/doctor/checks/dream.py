"""Doctor checks for Dream workspace readiness."""

from __future__ import annotations

from pathlib import Path

from nanobot.doctor.types import DoctorCheckResult, DoctorStatus

_SECTION = "dream"


def run_dream_checks(config, workspace: Path) -> list[DoctorCheckResult]:
    """Validate local Dream filesystem assumptions."""
    del config

    memory_dir = workspace / "memory"
    dream_cursor = memory_dir / ".dream_cursor"
    results: list[DoctorCheckResult] = []

    if memory_dir.exists():
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="dream_memory_dir",
                status=DoctorStatus.OK,
                message=f"Dream memory directory exists: {memory_dir}",
            )
        )
    else:
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="dream_memory_dir",
                status=DoctorStatus.WARN,
                message=f"Dream memory directory is missing: {memory_dir}",
                hint="Create workspace/memory before relying on Dream history state.",
            )
        )

    if dream_cursor.parent == memory_dir:
        status = DoctorStatus.OK if memory_dir.exists() else DoctorStatus.WARN
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="dream_cursor_parent",
                status=status,
                message=f"Dream cursor path resolves under memory/: {dream_cursor}",
            )
        )

    return results
