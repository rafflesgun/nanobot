"""Doctor checks for configured LLM providers."""

from __future__ import annotations

from nanobot.config.schema import Config, ProviderConfig
from nanobot.doctor.types import DoctorCheckResult, DoctorStatus
from nanobot.providers.registry import find_by_name

_SECTION = "providers"


def run_provider_checks(config: Config, *, live: bool) -> list[DoctorCheckResult]:
    """Validate the selected default provider using local config only."""
    agent = config.agents.defaults
    provider_name = config.get_provider_name(agent.model, agent=agent) or agent.provider
    results: list[DoctorCheckResult] = []

    spec = find_by_name(provider_name) if provider_name else None
    provider_cfg = getattr(config.providers, spec.name, None) if spec else None

    if spec is None or not isinstance(provider_cfg, ProviderConfig):
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="provider_config",
                status=DoctorStatus.FAIL,
                message=f"Selected provider is not configured in the registry: {provider_name!r}",
                hint="Set agents.defaults.provider to a known provider or use auto.",
            )
        )
        return results

    missing: list[str] = []
    if not spec.is_oauth and not spec.is_direct and not spec.is_local and not _has_value(provider_cfg.api_key):
        missing.append("api_key")
    if spec.backend == "azure_openai" and not _has_value(provider_cfg.api_base):
        missing.append("api_base")

    if missing:
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="provider_config",
                status=DoctorStatus.WARN,
                message=(
                    f"Provider '{spec.name}' is selected for model '{agent.model}' but is missing "
                    f"required config: {', '.join(missing)}"
                ),
                hint=f"Set providers.{spec.name}.{missing[0]} in config or environment.",
            )
        )
    else:
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="provider_config",
                status=DoctorStatus.OK,
                message=f"Provider '{spec.name}' is locally configured for model '{agent.model}'.",
            )
        )

    if live:
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="provider_live",
                status=DoctorStatus.WARN,
                message="Live provider probes are not implemented yet.",
                hint="This task only validates local provider configuration.",
            )
        )

    return results


def _has_value(value: str | None) -> bool:
    return bool(value and value.strip())
