from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.tools.spawn import SpawnTool
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import Config
from nanobot.providers.base import GenerationSettings, LLMResponse


def test_agents_config_resolve_named_agent_inherits_defaults() -> None:
    config = Config.model_validate(
        {
            "agents": {
                "defaults": {
                    "model": "main-model",
                    "provider": "openrouter",
                    "temperature": 0.4,
                    "maxTokens": 1111,
                    "reasoningEffort": "medium",
                },
                "research": {
                    "model": "research-model",
                    "temperature": 0.1,
                },
            }
        }
    )

    resolved = config.agents.resolve("research")

    assert resolved.model == "research-model"
    assert resolved.provider == "openrouter"
    assert resolved.temperature == 0.1
    assert resolved.max_tokens == 1111
    assert resolved.reasoning_effort == "medium"
    assert config.agents.agent_ids() == ["defaults", "research"]


def test_spawn_tool_exposes_subagent_selector_and_advertises_profiles() -> None:
    manager = MagicMock()
    manager.list_profiles.return_value = [
        {"id": "research", "label": "Research", "description": "fast web research"},
        {"id": "writer", "description": "polished writing"},
    ]

    tool = SpawnTool(manager=manager)

    assert "research" in tool.description
    assert "writer" in tool.description
    assert "subagent_id" in tool.parameters["properties"]


@pytest.mark.asyncio
async def test_spawn_tool_passes_subagent_id_to_manager() -> None:
    manager = MagicMock()
    manager.spawn = AsyncMock(return_value="started")

    tool = SpawnTool(manager=manager)
    tool.set_context("telegram", "123")

    result = await tool.execute("do it", label="research task", subagent_id="research")

    assert result == "started"
    manager.spawn.assert_awaited_once_with(
        task="do it",
        label="research task",
        origin_channel="telegram",
        origin_chat_id="123",
        session_key="telegram:123",
        subagent_id="research",
    )


@pytest.mark.asyncio
async def test_subagent_manager_uses_selected_agent_profile(tmp_path, monkeypatch) -> None:
    from nanobot.agent.subagent import SubagentManager

    config = Config.model_validate(
        {
            "agents": {
                "defaults": {
                    "model": "main-model",
                    "provider": "openrouter",
                    "temperature": 0.4,
                    "maxTokens": 1111,
                },
                "research": {
                    "model": "research-model",
                    "provider": "anthropic",
                    "temperature": 0.1,
                    "maxTokens": 2222,
                    "reasoningEffort": "high",
                },
            }
        }
    )

    created: list[tuple[str, GenerationSettings]] = []

    def provider_factory(agent_config):
        provider = MagicMock()
        provider.get_default_model.return_value = agent_config.model
        provider.generation = GenerationSettings(
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            reasoning_effort=agent_config.reasoning_effort,
        )
        provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="done", tool_calls=[]))
        created.append((agent_config.model, provider.generation))
        return provider

    mgr = SubagentManager(
        provider=MagicMock(),
        workspace=tmp_path,
        bus=MessageBus(),
        agents_config=config.agents,
        provider_factory=provider_factory,
    )

    monkeypatch.setattr(mgr, "_announce_result", AsyncMock(return_value=None))

    await mgr._run_subagent(
        "sub-1",
        "do task",
        "Research",
        {"channel": "test", "chat_id": "c1"},
        subagent_id="research",
    )

    assert created == [
        (
            "research-model",
            GenerationSettings(temperature=0.1, max_tokens=2222, reasoning_effort="high"),
        )
    ]
