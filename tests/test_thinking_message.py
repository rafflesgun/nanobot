"""Tests for Thinking… placeholder message – only in private chats."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from nanobot.channels.telegram import TelegramChannel
from nanobot.bus.events import OutboundMessage


@pytest.mark.asyncio
async def test_thinking_message_private_chat():
    """Test that thinking message is sent in private chats."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    
    # Mock the send_message method
    mock_message = AsyncMock()
    mock_message.message_id = 999
    channel._app.bot.send_message = AsyncMock(return_value=mock_message)
    
    await channel._send_thinking_message(chat_id=123456, is_group=False, thread_id=None)

    channel._app.bot.send_message.assert_called_once()
    call_args = channel._app.bot.send_message.call_args
    assert call_args.kwargs['chat_id'] == 123456
    assert call_args.kwargs['text'] == "💭 Thinking..."
    # Check that the composite key is used correctly (without thread_id)
    assert "123456" in channel._thinking_messages
    assert channel._thinking_messages["123456"] == 999


@pytest.mark.asyncio
async def test_no_thinking_message_in_group():
    """Test that thinking message is NOT sent in group chats."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    
    # Mock the send_message method
    channel._app.bot.send_message = AsyncMock(return_value=AsyncMock(message_id=999))

    await channel._send_thinking_message(chat_id=-100123456, is_group=True, thread_id=None)

    channel._app.bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_thinking_message_with_topic():
    """Test that thinking message works with topic threads in private chats."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    
    # Mock the send_message method
    mock_message = AsyncMock()
    mock_message.message_id = 1001
    channel._app.bot.send_message = AsyncMock(return_value=mock_message)
    
    await channel._send_thinking_message(chat_id=123456, is_group=False, thread_id=42)

    channel._app.bot.send_message.assert_called_once()
    call_args = channel._app.bot.send_message.call_args
    assert call_args.kwargs['chat_id'] == 123456
    assert call_args.kwargs['text'] == "💭 Thinking..."
    assert call_args.kwargs['message_thread_id'] == 42
    assert "123456:42" in channel._thinking_messages
    assert channel._thinking_messages["123456:42"] == 1001


@pytest.mark.asyncio
async def test_thinking_message_composite_key():
    """Test that the composite key mechanism works correctly."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    
    # Mock the send_message method
    mock_message = AsyncMock()
    mock_message.message_id = 2002
    channel._app.bot.send_message = AsyncMock(return_value=mock_message)
    
    # Test with different thread IDs to ensure separate keys
    await channel._send_thinking_message(chat_id=123456, is_group=False, thread_id=10)
    assert "123456:10" in channel._thinking_messages
    assert channel._thinking_messages["123456:10"] == 2002
    
    # Different thread ID should create different key
    mock_message2 = AsyncMock()
    mock_message2.message_id = 2003
    channel._app.bot.send_message = AsyncMock(return_value=mock_message2)
    
    await channel._send_thinking_message(chat_id=123456, is_group=False, thread_id=20)
    assert "123456:20" in channel._thinking_messages
    assert channel._thinking_messages["123456:20"] == 2003


@pytest.mark.asyncio
async def test_thinking_message_error_handling():
    """Test that thinking message handles errors gracefully."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    
    # Mock send_message to raise an exception
    channel._app.bot.send_message = AsyncMock(side_effect=Exception("API Error"))
    
    # Should not raise an exception even if API fails
    await channel._send_thinking_message(chat_id=123456, is_group=False, thread_id=None)
    
    # Still should have been called once
    channel._app.bot.send_message.assert_called_once()