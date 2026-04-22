"""Doctor checks for enabled channel configuration."""

from __future__ import annotations

from typing import Any

from nanobot.config.schema import Config
from nanobot.doctor.types import DoctorCheckResult, DoctorStatus

_SECTION = "channels"

_CHANNEL_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "telegram": ("token",),
    "discord": ("token",),
    "email": (
        "consent_granted",
        "imap_host",
        "imap_username",
        "imap_password",
        "smtp_host",
        "smtp_username",
        "smtp_password",
    ),
    "slack": ("bot_token", "app_token"),
    "feishu": ("app_id", "app_secret"),
    "dingtalk": ("client_id", "client_secret"),
    "matrix": ("homeserver", "user_id"),
    "mochat": ("claw_token",),
    "qq": ("app_id", "secret"),
    "wecom": ("bot_id", "secret"),
}


def run_channel_checks(config: Config, *, live: bool) -> list[DoctorCheckResult]:
    """Validate required fields only for enabled channels."""
    del live

    channels_extra = object.__getattribute__(config.channels, "__pydantic_extra__") or {}
    results: list[DoctorCheckResult] = []

    for name, raw_cfg in sorted(channels_extra.items()):
        if not isinstance(raw_cfg, dict) or not raw_cfg.get("enabled"):
            continue

        missing = [field for field in _CHANNEL_REQUIREMENTS.get(name, ()) if not _field_present(raw_cfg, field)]
        if missing:
            results.append(
                DoctorCheckResult(
                    section=_SECTION,
                    check_id=f"{name}_config",
                    status=DoctorStatus.WARN,
                    message=f"Enabled channel '{name}' is missing required fields: {', '.join(missing)}",
                    hint=f"Set the missing channels.{name} fields in config.",
                )
            )
            continue

        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id=f"{name}_config",
                status=DoctorStatus.OK,
                message=f"Enabled channel '{name}' has the required local configuration.",
            )
        )

    return results


def _field_present(cfg: dict[str, Any], field: str) -> bool:
    value = cfg.get(field)
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)
