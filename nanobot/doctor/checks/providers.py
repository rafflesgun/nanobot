"""Doctor checks for configured LLM providers."""

from __future__ import annotations

import asyncio

import httpx

from nanobot.config.schema import Config, ProviderConfig
from nanobot.doctor.types import DoctorCheckResult, DoctorStatus
from nanobot.providers.anthropic_provider import AnthropicProvider
from nanobot.providers.registry import find_by_name

_SECTION = "providers"
_PROBE_TIMEOUT_S = 5.0


def run_provider_checks(config: Config, *, live: bool) -> list[DoctorCheckResult]:
    """Validate the selected default provider using local config only."""
    agent = config.agents.defaults
    provider_name = config.get_provider_name(agent.model) or agent.provider
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
        ok, message = _probe_provider(config, spec.name)
        results.append(
            DoctorCheckResult(
                section=_SECTION,
                check_id="provider_live",
                status=DoctorStatus.OK if ok else DoctorStatus.FAIL,
                message=message,
                hint=None if ok else "Verify credentials, API base, and provider reachability.",
            )
        )

    return results


def _has_value(value: str | None) -> bool:
    return bool(value and value.strip())


def _probe_provider(config: Config, provider_name: str) -> tuple[bool, str]:
    try:
        return asyncio.run(_probe_provider_async(config, provider_name))
    except RuntimeError as exc:
        return False, f"Provider live probe failed: {exc}"
    except Exception as exc:
        return False, f"Provider live probe failed: {type(exc).__name__}: {exc}"


async def _probe_provider_async(config: Config, provider_name: str) -> tuple[bool, str]:
    spec = find_by_name(provider_name)
    if spec is None:
        return False, f"Provider live probe could not resolve provider '{provider_name}'."

    api_key = config.get_api_key(config.agents.defaults.model)
    api_base = config.get_api_base(agent=config.agents.defaults)
    provider_cfg = getattr(config.providers, spec.name, None)
    extra_headers = provider_cfg.extra_headers if isinstance(provider_cfg, ProviderConfig) else None

    if spec.backend == "anthropic":
        return await _probe_anthropic_provider(api_key, api_base, extra_headers)

    return await _probe_openai_compatible_provider(api_key, api_base, extra_headers)


async def _probe_openai_compatible_provider(
    api_key: str | None,
    api_base: str | None,
    extra_headers: dict[str, str] | None,
) -> tuple[bool, str]:
    if not api_base:
        return False, "Provider live probe could not determine an API base URL."

    headers = {**(extra_headers or {})}
    if api_key:
        headers.setdefault("Authorization", f"Bearer {api_key}")

    base = api_base.rstrip("/")
    async with httpx.AsyncClient(timeout=httpx.Timeout(_PROBE_TIMEOUT_S, connect=_PROBE_TIMEOUT_S)) as client:
        response = await client.get(f"{base}/models", headers=headers or None)
        response.raise_for_status()
    return True, "Provider live probe succeeded."


async def _probe_anthropic_provider(
    api_key: str | None,
    api_base: str | None,
    extra_headers: dict[str, str] | None,
) -> tuple[bool, str]:
    provider = AnthropicProvider(api_key=api_key, api_base=api_base, extra_headers=extra_headers)
    try:
        await asyncio.wait_for(provider._client.models.list(), timeout=_PROBE_TIMEOUT_S)
    finally:
        await provider._client.close()
    return True, "Provider live probe succeeded."
