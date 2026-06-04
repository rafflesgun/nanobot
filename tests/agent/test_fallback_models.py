from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import GenerationSettings, LLMResponse


def _make_loop(tmp_path, *, fallback_models=None) -> AgentLoop:
    provider = MagicMock()
    provider.get_default_model.return_value = "primary-model"
    provider.generation = GenerationSettings(max_tokens=0)

    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="primary-model",
        fallback_models=fallback_models,
    )
    loop.tools.get_definitions = MagicMock(return_value=[])
    return loop


@pytest.mark.asyncio
async def test_process_direct_tries_ordered_fallback_models_until_one_succeeds(tmp_path) -> None:
    loop = _make_loop(
        tmp_path,
        fallback_models=["legacy-fallback", "second-fallback", "third-fallback"],
    )

    seen_models: list[str] = []

    async def _chat_with_retry(**kwargs):
        model = kwargs["model"]
        seen_models.append(model)
        if model in {"primary-model", "legacy-fallback", "second-fallback"}:
            raise RuntimeError("Provider returned error: 503 temporarily unavailable")
        return LLMResponse(content=f"reply via {model}", tool_calls=[])

    loop.provider.chat_with_retry = _chat_with_retry
    loop.provider.chat_stream_with_retry = AsyncMock()

    response = await loop.process_direct("hello", session_key="cli:test")

    assert response is not None
    assert response.content == "reply via third-fallback"
    assert seen_models == [
        "primary-model",
        "legacy-fallback",
        "second-fallback",
        "third-fallback",
    ]


@pytest.mark.asyncio
async def test_process_direct_does_not_fallback_on_non_provider_error(tmp_path) -> None:
    loop = _make_loop(
        tmp_path,
        fallback_models=["legacy-fallback", "second-fallback"],
    )

    seen_models: list[str] = []

    async def _chat_with_retry(**kwargs):
        seen_models.append(kwargs["model"])
        raise RuntimeError("validation exploded before provider call")

    loop.provider.chat_with_retry = _chat_with_retry
    loop.provider.chat_stream_with_retry = AsyncMock()

    with pytest.raises(RuntimeError, match="validation exploded"):
        await loop.process_direct("hello", session_key="cli:test")

    assert seen_models == ["primary-model"]


@pytest.mark.asyncio
async def test_process_direct_falls_back_on_bare_429_error(tmp_path) -> None:
    loop = _make_loop(
        tmp_path,
        fallback_models=["fallback-model"],
    )

    seen_models: list[str] = []

    async def _chat_with_retry(**kwargs):
        model = kwargs["model"]
        seen_models.append(model)
        if model == "primary-model":
            raise RuntimeError("429 rate limit")
        return LLMResponse(content=f"reply via {model}", tool_calls=[])

    loop.provider.chat_with_retry = _chat_with_retry
    loop.provider.chat_stream_with_retry = AsyncMock()

    response = await loop.process_direct("hello", session_key="cli:test")

    assert response is not None
    assert response.content == "reply via fallback-model"
    assert seen_models == ["primary-model", "fallback-model"]


@pytest.mark.asyncio
async def test_process_direct_falls_back_on_temporarily_unavailable_error(tmp_path) -> None:
    loop = _make_loop(
        tmp_path,
        fallback_models=["fallback-model"],
    )

    seen_models: list[str] = []

    async def _chat_with_retry(**kwargs):
        model = kwargs["model"]
        seen_models.append(model)
        if model == "primary-model":
            raise RuntimeError(
                "Error: {'message': 'Service temporarily unavailable', 'type': 'api_error', 'param': '', 'code': None}"
            )
        return LLMResponse(content=f"reply via {model}", tool_calls=[])

    loop.provider.chat_with_retry = _chat_with_retry
    loop.provider.chat_stream_with_retry = AsyncMock()

    response = await loop.process_direct("hello", session_key="cli:test")

    assert response is not None
    assert response.content == "reply via fallback-model"
    assert seen_models == ["primary-model", "fallback-model"]


def test_raw_model_id_fallback_in_factory() -> None:
    """Raw model IDs (not in model_presets) work as fallback entries."""
    from nanobot.config.schema import Config
    from nanobot.providers.factory import _resolve_fallback_presets

    config = Config.model_validate({
        "agents": {
            "defaults": {
                "model": "nvd-qwen-3.5-122b",
                "fallbackModels": ["nvd-kimi-k26", "op-gemma-4"],
                "provider": "custom",
            },
        },
        "modelPresets": {},
    })
    primary = config.resolve_preset()
    presets = _resolve_fallback_presets(config, primary)

    assert len(presets) == 2
    assert presets[0].model == "nvd-kimi-k26"
    assert presets[0].provider == "custom"
    assert presets[1].model == "op-gemma-4"
    assert presets[1].provider == "custom"


def test_mixed_preset_refs_and_raw_ids_in_fallback() -> None:
    """Fallback list can mix preset refs and raw model IDs."""
    from nanobot.config.schema import Config
    from nanobot.providers.factory import _resolve_fallback_presets

    config = Config.model_validate({
        "agents": {
            "defaults": {
                "model": "main",
                "fallbackModels": ["helper", "raw-gpt-5"],
                "provider": "openai",
            },
        },
        "modelPresets": {
            "helper": {"model": "gpt-4o-mini", "provider": "openai", "temperature": 0.5},
        },
    })
    primary = config.resolve_preset()
    presets = _resolve_fallback_presets(config, primary)

    assert len(presets) == 2
    assert presets[0].model == "gpt-4o-mini"
    assert presets[0].temperature == 0.5
    assert presets[1].model == "raw-gpt-5"
    assert presets[1].provider == "openai"
