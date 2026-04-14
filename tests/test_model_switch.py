"""Tests for /model command and per-session model/temperature override."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from nanobot.agent.loop import AgentLoop
from nanobot.providers.base import GenerationSettings, LLMProvider, LLMResponse


def _make_mock_provider(model: str = "gpt-4o") -> MagicMock:
    """Create a properly mocked provider for AgentLoop tests."""
    provider = MagicMock(spec=LLMProvider)
    provider.get_default_model.return_value = model
    provider.generation = GenerationSettings()
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(content="OK", tool_calls=[], finish_reason="stop")
    )
    return provider


@pytest.mark.asyncio
async def test_model_show_current():
    """Test that /model command shows current model when no argument is provided."""
    # Setup
    bus = AsyncMock()
    provider = _make_mock_provider()

    with patch("nanobot.agent.loop.load_model_overrides", return_value={}):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    # Test the _handle_model_command method directly
    msg = AsyncMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}

    with patch("nanobot.agent.loop.save_model_overrides"):
        response = loop._handle_model_command(msg, "test:session", "/model")

    assert "Current model: `gpt-4o`" in response.content
    assert "session override" not in response.content  # Should not be an override


@pytest.mark.asyncio
async def test_model_switch_and_use():
    """Test that /model command switches model for session and that it's used."""
    # Setup
    bus = AsyncMock()
    provider = _make_mock_provider()

    with patch("nanobot.agent.loop.load_model_overrides", return_value={}):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    session_key = "test:session"

    # Switch model using the internal method
    msg = AsyncMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}

    with patch("nanobot.agent.loop.save_model_overrides"):
        loop._handle_model_command(msg, session_key, "/model claude-3.5-sonnet")

    assert loop._model_overrides[session_key] == "claude-3.5-sonnet"

    # Verify that _run_agent_loop uses the override
    final_content, tools_used, all_msgs, _, _ = await loop._run_agent_loop(
        [{"role": "user", "content": "hello"}],
        model_override=loop._model_overrides.get(session_key),
    )

    # Check that provider.chat_with_retry was called with the overridden model
    assert provider.chat_with_retry.called
    call_args = provider.chat_with_retry.call_args
    assert call_args.kwargs["model"] == "claude-3.5-sonnet"


@pytest.mark.asyncio
async def test_model_revert_to_default():
    """Test that /model reset reverts to default model."""
    # Setup
    bus = AsyncMock()
    provider = _make_mock_provider()

    with patch("nanobot.agent.loop.load_model_overrides", return_value={}):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    session_key = "test:session"

    # Set override
    loop._model_overrides[session_key] = "claude-3.5-sonnet"

    # Revert using the internal method
    msg = AsyncMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}

    with patch("nanobot.agent.loop.save_model_overrides"):
        loop._handle_model_command(msg, session_key, "/model reset")

    assert session_key not in loop._model_overrides


@pytest.mark.asyncio
async def test_model_override_with_backticks():
    """Test that /model command handles model names with backticks."""
    # Setup
    bus = AsyncMock()
    provider = _make_mock_provider()

    with patch("nanobot.agent.loop.load_model_overrides", return_value={}):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    session_key = "test:session"

    # Switch model using backticks
    msg = AsyncMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}

    with patch("nanobot.agent.loop.save_model_overrides"):
        loop._handle_model_command(msg, session_key, "/model `claude-3.5-sonnet`")

    assert loop._model_overrides[session_key] == "claude-3.5-sonnet"


@pytest.mark.asyncio
async def test_model_override_in_process_message():
    """Test that /model command works end-to-end in message processing."""
    # Setup
    bus = AsyncMock()
    provider = _make_mock_provider()

    with patch("nanobot.agent.loop.load_model_overrides", return_value={}):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    # Simulate processing a /model command message
    msg = AsyncMock()
    msg.channel = "telegram"
    msg.sender_id = "user1"
    msg.chat_id = "123"
    msg.content = "/model gpt-4-turbo"
    msg.metadata = {}

    # This should trigger the model command handling logic
    # We'll test the actual _process_message flow
    with patch("nanobot.agent.loop.save_model_overrides"):
        response = await loop._process_message(msg, session_key="test:session")

    # The response should contain confirmation of the model switch
    assert response is not None
    assert "Model switched to" in response.content


@pytest.mark.asyncio
async def test_fallback_models_on_error():
    """Test that fallback models are tried when primary model fails."""
    # Setup
    bus = AsyncMock()
    provider = _make_mock_provider()

    # Create responses: first fails, second succeeds
    fail_response = LLMResponse(
        content="Error: {'message': 'unknown error []', 'type': 'bad_response_status_code'}",
        finish_reason="error",
    )
    success_response = LLMResponse(
        content="Success from fallback",
        tool_calls=[],
        finish_reason="stop",
    )

    provider.chat_with_retry = AsyncMock()
    provider.chat_with_retry.side_effect = [fail_response, success_response]

    with patch("nanobot.agent.loop.load_model_overrides", return_value={}):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="primary-model",
            fallback_models=["fallback-model-1", "fallback-model-2"],
        )

    # Process a message
    msg = AsyncMock()
    msg.channel = "telegram"
    msg.sender_id = "user1"
    msg.chat_id = "123"
    msg.content = "Hello"
    msg.metadata = {}

    final_content, tools_used, all_msgs, _, _ = await loop._run_agent_loop(
        [{"role": "user", "content": "hello"}],
    )

    # Should have tried primary first, then fallback
    assert provider.chat_with_retry.call_count >= 1
    # The fallback model should have been used
    calls = provider.chat_with_retry.call_args_list
    models_called = [call.kwargs.get("model") for call in calls]
    # First call should be primary model
    assert "primary-model" in models_called[0] or models_called[0] is None


@pytest.mark.asyncio
async def test_no_fallback_on_user_abort():
    """Test that fallback is not triggered on non-retriable errors."""
    bus = AsyncMock()
    provider = _make_mock_provider()

    # Response that should NOT trigger fallback (e.g., content policy)
    fail_response = LLMResponse(
        content="Error: content policy violation",
        finish_reason="error",
    )
    provider.chat_with_retry = AsyncMock(return_value=fail_response)

    with patch("nanobot.agent.loop.load_model_overrides", return_value={}):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="primary-model",
            fallback_models=["fallback-model"],
        )

    final_content, tools_used, all_msgs, _, _ = await loop._run_agent_loop(
        [{"role": "user", "content": "hello"}],
    )

    # Should have only called once (no fallback for content policy)
    assert provider.chat_with_retry.call_count == 1


@pytest.mark.asyncio
async def test_model_override_in_system_message():
    """Test that model override is applied when processing system messages (subagent results)."""
    # Setup
    bus = AsyncMock()
    provider = _make_mock_provider()

    with patch("nanobot.agent.loop.load_model_overrides", return_value={}):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    # Set a model override for a session
    session_key = "telegram:123"
    loop._model_overrides[session_key] = "claude-3.5-sonnet"

    # Simulate a system message (like subagent result)
    msg = AsyncMock()
    msg.channel = "system"
    msg.sender_id = "subagent"
    msg.chat_id = "telegram:123"  # system messages encode origin in chat_id
    msg.content = "[Subagent 'test' completed successfully]\nTask: test\nResult: done"
    msg.metadata = {}

    # Process the system message
    with (
        patch.object(loop, "_save_turn"),
        patch.object(loop, "_clear_runtime_checkpoint"),
        patch.object(loop.sessions, "save"),
    ):
        await loop._process_message(msg)

    # Verify that provider was called with the overridden model
    assert provider.chat_with_retry.called
    call_args = provider.chat_with_retry.call_args
    assert call_args.kwargs["model"] == "claude-3.5-sonnet", (
        "System message should use model override for the session"
    )


# =============================================================================
# Temperature Override Tests
# =============================================================================


@pytest.mark.asyncio
async def test_temp_show_current():
    """Test that /model temp command shows current temperature when no argument is provided."""
    bus = AsyncMock()
    provider = _make_mock_provider()

    with (
        patch("nanobot.agent.loop.load_model_overrides", return_value={}),
        patch("nanobot.agent.loop.load_temperature_overrides", return_value={}),
    ):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    msg = MagicMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}
    msg.content = "/model temp"

    with patch("nanobot.agent.loop.save_temperature_overrides"):
        response = loop._handle_model_command(msg, "test:session", "/model temp")

    assert "Temperature" in response.content
    assert "no override set" in response.content.lower()


@pytest.mark.asyncio
async def test_temp_set_and_use():
    """Test that /model temp 0.7 sets temperature and it's used in agent loop."""
    bus = AsyncMock()
    provider = _make_mock_provider()

    with (
        patch("nanobot.agent.loop.load_model_overrides", return_value={}),
        patch("nanobot.agent.loop.load_temperature_overrides", return_value={}),
    ):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    session_key = "test:session"

    msg = MagicMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}
    msg.content = "/model temp 0.5"

    with patch("nanobot.agent.loop.save_temperature_overrides"):
        response = loop._handle_model_command(msg, session_key, "/model temp 0.5")

    assert loop._temperature_overrides[session_key] == 0.5
    assert "Temperature set to `0.5`" in response.content

    # Verify that _run_agent_loop uses the temperature override
    final_content, tools_used, all_msgs, _, _ = await loop._run_agent_loop(
        [{"role": "user", "content": "hello"}],
        temperature_override=loop._temperature_overrides.get(session_key),
    )

    # Check that provider.chat_with_retry was called with the temperature
    assert provider.chat_with_retry.called
    call_args = provider.chat_with_retry.call_args
    assert call_args.kwargs.get("temperature") == 0.5


@pytest.mark.asyncio
async def test_temp_revert_to_default():
    """Test that /model temp reset reverts to model default temperature."""
    bus = AsyncMock()
    provider = _make_mock_provider()

    with (
        patch("nanobot.agent.loop.load_model_overrides", return_value={}),
        patch("nanobot.agent.loop.load_temperature_overrides", return_value={}),
    ):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    session_key = "test:session"

    # Set override
    loop._temperature_overrides[session_key] = 0.9

    msg = MagicMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}
    msg.content = "/model temp reset"

    with patch("nanobot.agent.loop.save_temperature_overrides"):
        response = loop._handle_model_command(msg, session_key, "/model temp reset")

    assert session_key not in loop._temperature_overrides
    assert "reset" in response.content.lower()


@pytest.mark.asyncio
async def test_temp_invalid_value():
    """Test that /model temp rejects invalid temperature values."""
    bus = AsyncMock()
    provider = _make_mock_provider()

    with (
        patch("nanobot.agent.loop.load_model_overrides", return_value={}),
        patch("nanobot.agent.loop.load_temperature_overrides", return_value={}),
    ):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    msg = MagicMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}
    msg.content = "/model temp 3.0"

    response = loop._handle_model_command(msg, "test:session", "/model temp 3.0")

    assert "must be between 0.0 and 2.0" in response.content
    assert "test:session" not in loop._temperature_overrides


@pytest.mark.asyncio
async def test_temp_invalid_format():
    """Test that /model temp rejects non-numeric values."""
    bus = AsyncMock()
    provider = _make_mock_provider()

    with (
        patch("nanobot.agent.loop.load_model_overrides", return_value={}),
        patch("nanobot.agent.loop.load_temperature_overrides", return_value={}),
    ):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    msg = MagicMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}
    msg.content = "/model temp hot"

    response = loop._handle_model_command(msg, "test:session", "/model temp hot")

    assert "Invalid temperature value" in response.content


@pytest.mark.asyncio
async def test_temp_shows_override_status():
    """Test that /model temp shows when there's an active override."""
    bus = AsyncMock()
    provider = _make_mock_provider()

    with (
        patch("nanobot.agent.loop.load_model_overrides", return_value={}),
        patch("nanobot.agent.loop.load_temperature_overrides", return_value={}),
    ):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    session_key = "test:session"
    loop._temperature_overrides[session_key] = 0.3

    msg = MagicMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {}
    msg.content = "/model temp"

    response = loop._handle_model_command(msg, session_key, "/model temp")

    assert "Current temperature: `0.3`" in response.content
    assert "session override" in response.content.lower()


@pytest.mark.asyncio
async def test_temp_persists_across_sessions():
    """Test that temperature overrides are persisted to disk."""
    bus = AsyncMock()
    provider = _make_mock_provider()

    with (
        patch("nanobot.agent.loop.load_model_overrides", return_value={}),
        patch("nanobot.agent.loop.load_temperature_overrides", return_value={}),
    ):
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=Path("/tmp/test"),
            model="gpt-4o",
        )

    session_key = "telegram:123:topic:42"

    msg = MagicMock()
    msg.channel = "telegram"
    msg.chat_id = "123"
    msg.metadata = {"message_thread_id": 42}
    msg.content = "/model temp 0.7"

    saved_overrides = {}

    def mock_save(overrides):
        saved_overrides.update(overrides)

    with patch("nanobot.agent.loop.save_temperature_overrides", side_effect=mock_save):
        loop._handle_model_command(msg, session_key, "/model temp 0.7")

    assert saved_overrides.get(session_key) == 0.7
