"""Doctor report aggregation service."""

from __future__ import annotations

import json
from pathlib import Path

from nanobot.config.loader import resolve_config_env_vars
from nanobot.config.schema import Config
from nanobot.doctor.checks.channels import run_channel_checks
from nanobot.doctor.checks.config import run_config_checks
from nanobot.doctor.checks.dream import run_dream_checks
from nanobot.doctor.checks.mcp import run_mcp_checks
from nanobot.doctor.checks.providers import run_provider_checks
from nanobot.doctor.checks.skills import run_skill_checks
from nanobot.doctor.checks.workspace import run_workspace_checks
from nanobot.doctor.types import DoctorReport


class DoctorService:
    def run(self, *, config_path: Path | None, workspace: Path | None, live: bool) -> DoctorReport:
        resolved_config_path = (config_path or Path("config.json")).expanduser().resolve(strict=False)
        resolved_workspace = (workspace or Path(".")).expanduser().resolve(strict=False)

        results = []
        results.extend(run_config_checks(resolved_config_path))
        results.extend(run_workspace_checks(resolved_workspace))

        config = self._load_valid_config(resolved_config_path)
        if config is not None:
            results.extend(run_provider_checks(config, live=live))
            results.extend(run_channel_checks(config, live=live))
            results.extend(run_dream_checks(config, resolved_workspace))
            results.extend(run_skill_checks(resolved_workspace))
            results.extend(run_mcp_checks(config, live=live))

        return DoctorReport(
            mode="live" if live else "local",
            config_path=str(resolved_config_path),
            workspace_path=str(resolved_workspace),
            results=results,
        )

    def _load_valid_config(self, config_path: Path) -> Config | None:
        try:
            with open(config_path, encoding="utf-8") as handle:
                raw = json.load(handle)
            return resolve_config_env_vars(Config.model_validate(raw))
        except Exception:
            return None
