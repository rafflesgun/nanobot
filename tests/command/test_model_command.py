from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import nanobot.agent.loop as agent_loop
from nanobot.agent.goal_permission import goal_mutation_allowed
from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.command.builtin import (
    build_help_text,
    builtin_command_palette,
    cmd_goal,
    cmd_model,
    register_builtin_commands,
)
from nanobot.command.router import CommandContext, CommandRouter
from nanobot.config.schema import ModelPresetConfig


def _provider(default_model: str, max_tokens: int = 123) -> MagicMock:
    provider = MagicMock()
    provider.get_default_model.return_value = default_model
    provider.generation = SimpleNamespace(
        max_tokens=max_tokens,
        temperature=0.1,
        reasoning_effort=None,
    )
    return provider


@pytest.fixture(autouse=True)
def isolate_model_override_store(monkeypatch) -> None:
    monkeypatch.setattr(agent_loop, "load_model_overrides", lambda: {})
    monkeypatch.setattr(agent_loop, "save_model_overrides", lambda _overrides: None)
    monkeypatch.setattr(agent_loop, "load_temperature_overrides", lambda: {})
    monkeypatch.setattr(agent_loop, "save_temperature_overrides", lambda _overrides: None)


def _make_loop(tmp_path) -> AgentLoop:
    return AgentLoop(
        bus=MessageBus(),
        provider=_provider("base-model", max_tokens=123),
        workspace=tmp_path,
        model="base-model",
        context_window_tokens=1000,
        model_presets={
            "default": ModelPresetConfig(
                model="base-model",
                max_tokens=123,
                context_window_tokens=1000,
            ),
            "fast": ModelPresetConfig(
                model="openai/gpt-4.1",
                max_tokens=4096,
                context_window_tokens=32_768,
            ),
        },
    )


def _ctx(
    loop: AgentLoop,
    raw: str,
    args: str = "",
    *,
    key: str | None = None,
    metadata: dict | None = None,
) -> CommandContext:
    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="direct",
        content=raw,
        metadata=metadata or {},
    )
    return CommandContext(msg=msg, session=None, key=key or msg.session_key, raw=raw, args=args, loop=loop)


def _ctx_session(loop: AgentLoop, raw: str, args: str = "") -> CommandContext:
    msg = InboundMessage(channel="cli", sender_id="user", chat_id="direct", content=raw)
    return CommandContext(
        msg=msg, session=MagicMock(), key=msg.session_key, raw=raw, args=args, loop=loop,
        is_user_turn=True,
    )


@pytest.mark.asyncio
async def test_model_command_shows_session_override_status(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    loop._model_overrides["cli:direct"] = "session-model"

    out = await cmd_model(_ctx(loop, "/model"))

    assert "Current model: `session-model`" in out.content
    assert "session override" in out.content
    assert out.metadata == {"command_response": True}


@pytest.mark.asyncio
async def test_model_command_sets_session_override_when_name_matches_preset(tmp_path) -> None:
    loop = _make_loop(tmp_path)

    out = await cmd_model(_ctx(loop, "/model fast", args="fast"))

    assert "Model switched to `fast` for this session" in out.content
    assert loop._model_overrides == {"cli:direct": "fast"}
    assert loop.model_preset is None
    assert loop.model == "base-model"


@pytest.mark.asyncio
async def test_model_command_reset_removes_session_override(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    loop._model_overrides["cli:direct"] = "session-model"

    out = await cmd_model(_ctx(loop, "/model reset", args="reset"))

    assert "Model reset to default: `base-model`" in out.content
    assert loop._model_overrides == {}
    assert loop.model_preset is None
    assert loop.model == "base-model"


@pytest.mark.asyncio
async def test_model_command_accepts_unconfigured_model_name(tmp_path) -> None:
    loop = _make_loop(tmp_path)

    out = await cmd_model(_ctx(loop, "/model missing", args="missing"))

    assert "Model switched to `missing` for this session" in out.content
    assert loop._model_overrides == {"cli:direct": "missing"}
    assert loop.model_preset is None
    assert loop.model == "base-model"


@pytest.mark.asyncio
async def test_model_command_sets_temperature_without_changing_model_override(tmp_path) -> None:
    loop = _make_loop(tmp_path)

    out = await cmd_model(_ctx(loop, "/model temp 0.7", args="temp 0.7"))

    assert "Temperature set to `0.7` for this session" in out.content
    assert loop._temperature_overrides == {"cli:direct": 0.7}
    assert loop._model_overrides == {}


@pytest.mark.asyncio
async def test_model_command_registered_as_exact_and_prefix(tmp_path) -> None:
    router = CommandRouter()
    register_builtin_commands(router)
    loop = _make_loop(tmp_path)

    out = await router.dispatch(_ctx(loop, "/model raw-model"))

    assert out is not None
    assert out.channel == "cli"
    assert out.chat_id == "direct"
    assert out.metadata == {"command_response": True}
    assert "Model switched to `raw-model` for this session" in out.content
    assert loop._model_overrides == {"cli:direct": "raw-model"}


@pytest.mark.asyncio
async def test_model_command_preserves_topic_metadata(tmp_path) -> None:
    loop = _make_loop(tmp_path)

    out = await cmd_model(
        _ctx(
            loop,
            "/model topic-model",
            args="topic-model",
            key="cli:direct:topic:42",
            metadata={"message_thread_id": 42},
        )
    )

    assert out.metadata == {"message_thread_id": 42, "command_response": True}
    assert loop._model_overrides == {"cli:direct:topic:42": "topic-model"}


def test_model_command_in_help_and_palette() -> None:
    palette = builtin_command_palette()

    model = next(item for item in palette if item["command"] == "/model")
    assert model["arg_hint"] == "[model-id|reset|temp]"
    assert model["lifecycle"] == "side_channel"
    assert model["accepts_args"] is True
    assert "/model [model-id|reset|temp]" in build_help_text()


@pytest.mark.asyncio
async def test_goal_command_shows_usage_without_args(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    out = await cmd_goal(_ctx(loop, "/goal"))
    assert out is not None
    assert out.channel == "cli"
    assert out.chat_id == "direct"
    assert out.metadata == {"render_as": "text"}
    assert out.content == "Usage: /goal <long-running task description>"


@pytest.mark.asyncio
async def test_goal_command_rejects_mid_turn_without_session(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    out = await cmd_goal(_ctx(loop, "/goal do work", args="do work"))
    assert out is not None
    assert out.channel == "cli"
    assert out.chat_id == "direct"
    assert out.metadata == {"render_as": "text"}
    assert out.content == (
        "A task is already running for this chat. "
        "Use `/stop` first, then send `/goal <long-running task description>` again."
    )


@pytest.mark.asyncio
async def test_goal_command_marks_turn_and_preserves_explicit_request(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    ctx = _ctx_session(loop, "/goal audit the repo", args="audit the repo")
    out = await cmd_goal(ctx)
    assert out is None
    assert ctx.msg.content == "/goal audit the repo"
    assert ctx.msg.metadata.get("original_command") == "/goal"
    assert ctx.msg.metadata.get("original_content") == "/goal audit the repo"
    assert ctx.msg.metadata.get("goal_requested") is True
    assert isinstance(ctx.msg.metadata.get("goal_started_at"), int | float)
    assert len(ctx.turn_scopes) == 1
    with ctx.turn_scopes[0]:
        assert goal_mutation_allowed() is True
    assert goal_mutation_allowed() is False


@pytest.mark.asyncio
async def test_goal_command_registered_on_router(tmp_path) -> None:
    router = CommandRouter()
    register_builtin_commands(router)
    loop = _make_loop(tmp_path)
    ctx = _ctx_session(loop, "/goal ship it", args="ship it")
    out = await router.dispatch(ctx)
    assert out is None
    assert "ship it" in ctx.msg.content
    assert len(ctx.turn_scopes) == 1
    with ctx.turn_scopes[0]:
        assert goal_mutation_allowed() is True
    assert goal_mutation_allowed() is False


@pytest.mark.asyncio
async def test_goal_command_does_not_allow_internal_turn(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    ctx = CommandContext(
        msg=InboundMessage(
            channel="cli",
            sender_id="system",
            chat_id="direct",
            content="/goal internal work",
        ),
        session=MagicMock(),
        key="cli:direct",
        raw="/goal internal work",
        args="internal work",
        loop=loop,
        is_user_turn=False,
    )

    out = await cmd_goal(ctx)

    assert out is not None
    assert "only be started by a user" in out.content
    assert ctx.turn_scopes == []


def test_goal_command_in_help_and_palette() -> None:
    palette = builtin_command_palette()
    goal = next(item for item in palette if item["command"] == "/goal")
    assert goal["arg_hint"] == "<goal>"
    assert goal["lifecycle"] == "agent_turn_with_args"
    assert goal["accepts_args"] is True
    assert "/goal <goal>" in build_help_text()
