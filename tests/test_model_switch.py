"""Tests for /model command and per-session model override."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from nanobot.agent.loop import AgentLoop
from nanobot.providers.base import LLMProvider, LLMResponse


@pytest.mark.asyncio
async def test_model_show_current():
    """Test that /model command shows current model when no argument is provided."""
    # Setup
    bus = AsyncMock()
    provider = AsyncMock(spec=LLMProvider)
    provider.get_default_model.return_value = "gpt-4o"
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="OK", tool_calls=[], finish_reason="stop"))

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
    provider = AsyncMock(spec=LLMProvider)
    provider.get_default_model.return_value = "gpt-4o"
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="OK", tool_calls=[], finish_reason="stop"))

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
    provider = AsyncMock(spec=LLMProvider)
    provider.get_default_model.return_value = "gpt-4o"
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="OK", tool_calls=[], finish_reason="stop"))

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
    provider = AsyncMock(spec=LLMProvider)
    provider.get_default_model.return_value = "gpt-4o"
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="OK", tool_calls=[], finish_reason="stop"))

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
    provider = AsyncMock(spec=LLMProvider)
    provider.get_default_model.return_value = "gpt-4o"
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(content="OK", tool_calls=[], finish_reason="stop"))

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