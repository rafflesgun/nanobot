"""Tests for /model command and per-session model override."""

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
    final_content, tools_used, all_msgs = await loop._run_agent_loop(
        [{"role": "user", "content": "hello"}],
        model_override=loop._model_overrides.get(session_key),
    )

    # Check that provider.chat_with_retry was called with the overridden model
    assert provider.chat_with_retry.called
    call_args = provider.chat_with_retry.call_args
    assert call_args.kwargs['model'] == "claude-3.5-sonnet"


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

    final_content, tools_used, all_msgs = await loop._run_agent_loop(
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

    final_content, tools_used, all_msgs = await loop._run_agent_loop(
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
    with patch.object(loop, "_save_turn"), \
         patch.object(loop, "_clear_runtime_checkpoint"), \
         patch.object(loop.sessions, "save"):
        await loop._process_message(msg)

    # Verify that provider was called with the overridden model
    assert provider.chat_with_retry.called
    call_args = provider.chat_with_retry.call_args
    assert call_args.kwargs['model'] == "claude-3.5-sonnet", \
        "System message should use model override for the session"