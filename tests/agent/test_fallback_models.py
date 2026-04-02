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
@pytest.mark.skip(reason="Fallback models need to be integrated at AgentRunner level after PR #2733 merge")
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

