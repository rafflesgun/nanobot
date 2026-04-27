"""Doctor checks for nanobot configuration files."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pydantic

from nanobot.config.schema import Config
from nanobot.doctor.types import DoctorCheckResult, DoctorStatus

_SECTION = "config"

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def run_config_checks(config_path: Path) -> list[DoctorCheckResult]:
    """Run all configuration-file checks and return results.

    Checks performed:
    - config_exists: does the file exist?
    - config_parse: does it parse as valid JSON?
    - config_validate: does it pass Pydantic schema validation?
    - env_resolution: can all ``${VAR}`` references resolve?
    """
    results: list[DoctorCheckResult] = []

    # ── config_exists ──
    if not config_path.exists():
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="config_exists",
                status=DoctorStatus.FAIL,
                message=f"Config file not found: {config_path}",
                hint="Create a config file or run with --init to generate one.",
            )
        )
        return results

    results.append(
        DoctorCheckResult(
            section=_SECTION,
            check_id="config_exists",
            status=DoctorStatus.OK,
            message=f"Config file found: {config_path}",
        )
    )

    # ── config_parse ──
    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="config_parse",
                status=DoctorStatus.FAIL,
                message=f"Config file is not valid JSON: {exc}",
                hint="Fix the JSON syntax in your config file.",
            )
        )
        return results

    results.append(
        DoctorCheckResult(
            section=_SECTION,
            check_id="config_parse",
            status=DoctorStatus.OK,
            message="Config file is valid JSON.",
        )
    )

    # ── config_validate ──
    try:
        config = Config.model_validate(data)
    except pydantic.ValidationError as exc:
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="config_validate",
                status=DoctorStatus.FAIL,
                message=f"Config schema validation failed: {exc}",
                hint="Check field types and values against the config schema.",
            )
        )
        return results

    results.append(
        DoctorCheckResult(
            section=_SECTION,
            check_id="config_validate",
            status=DoctorStatus.OK,
            message="Config passes schema validation.",
        )
    )

    # ── env_resolution ──
    unresolved = _find_unresolved_env_vars(config.model_dump(mode="json", by_alias=True))
    if unresolved:
        missing = ", ".join(sorted(unresolved))
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="env_resolution",
                status=DoctorStatus.FAIL,
                message=f"Unresolved environment variables: {missing}",
                hint="Set the missing environment variables or remove the references.",
            )
        )
    else:
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="env_resolution",
                status=DoctorStatus.OK,
                message="All environment variable references can be resolved.",
            )
        )

    return results


def _find_unresolved_env_vars(obj: object) -> set[str]:
    """Recursively find ``${VAR}`` references whose variables are not set."""
    missing: set[str] = set()
    if isinstance(obj, str):
        for match in _ENV_VAR_PATTERN.finditer(obj):
            name = match.group(1)
            if os.environ.get(name) is None:
                missing.add(name)
    elif isinstance(obj, dict):
        for v in obj.values():
            missing |= _find_unresolved_env_vars(v)
    elif isinstance(obj, list):
        for v in obj:
            missing |= _find_unresolved_env_vars(v)
    return missing
