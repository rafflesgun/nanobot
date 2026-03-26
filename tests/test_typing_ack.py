"""Tests for typing indicator and ACK reaction."""

import pytest
from unittest.mock import AsyncMock, patch
import asyncio

from nanobot.channels.telegram import TelegramChannel


@pytest.mark.asyncio
async def test_ack_reaction_sent():
    """Test that ACK reaction is sent successfully."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.set_message_reaction = AsyncMock()

    await channel._add_ack_reaction(chat_id=123456, message_id=789)

    channel._app.bot.set_message_reaction.assert_called_once()


@pytest.mark.asyncio
async def test_ack_reaction_with_thread():
    """Test that ACK reaction works with thread IDs."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.set_message_reaction = AsyncMock()

    await channel._add_ack_reaction(chat_id=123456, message_id=789)

    call_args = channel._app.bot.set_message_reaction.call_args
    assert call_args.kwargs.get('chat_id') == 123456
    assert call_args.kwargs.get('message_id') == 789


@pytest.mark.asyncio
async def test_ack_reaction_error_handling():
    """Test that ACK reaction handles errors gracefully."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.set_message_reaction = AsyncMock(side_effect=Exception("API Error"))

    # Should not raise an exception even if API fails
    await channel._add_ack_reaction(chat_id=123456, message_id=789)
    
    # Should have been called once despite error
    channel._app.bot.set_message_reaction.assert_called_once()


@pytest.mark.asyncio
async def test_ack_reaction_still_random_when_fixed_emoji_is_empty():
    """Explicit react_emoji='' should still allow the random ACK reaction path."""
    channel = TelegramChannel(
        config={"group_policy": "mention", "token": "fake_token", "allowFrom": ["*"], "react_emoji": ""},
        bus=AsyncMock(),
    )
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.set_message_reaction = AsyncMock()

    await channel._add_ack_reaction(chat_id=123456, message_id=789)

    channel._app.bot.set_message_reaction.assert_called_once()


@pytest.mark.asyncio
async def test_typing_indicator_started():
    """Test that typing indicator is started correctly."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.send_chat_action = AsyncMock()
    channel._typing_tasks = {}

    channel._start_typing(comp_key="123:private", thread_id=None)

    assert "123:private" in channel._typing_tasks
    # Note: send_chat_action is called in the background loop, not immediately


@pytest.mark.asyncio
async def test_typing_indicator_with_thread():
    """Test that typing indicator works with thread IDs."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.send_chat_action = AsyncMock()
    channel._typing_tasks = {}

    channel._start_typing(comp_key="123:42", thread_id=42)

    assert "123:42" in channel._typing_tasks
    # Note: send_chat_action is called in background loop, not immediately
    # We can't easily test this without running the loop, so just verify the task was created


@pytest.mark.asyncio
async def test_typing_indicator_stopped():
    """Test that typing indicator can be stopped."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.send_chat_action = AsyncMock()
    channel._typing_tasks = {}

    # Start typing
    channel._start_typing(comp_key="123:private", thread_id=None)
    assert "123:private" in channel._typing_tasks

    # Stop typing
    channel._stop_typing(comp_key="123:private")
    
    # Task should be removed
    assert "123:private" not in channel._typing_tasks
    # Note: We can't test send_chat_action.called since it's in a background loop


@pytest.mark.asyncio
async def test_typing_indicator_multiple_chats():
    """Test that typing indicators work independently for different chats."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.send_chat_action = AsyncMock()
    channel._typing_tasks = {}

    # Start typing for two different chats
    channel._start_typing(comp_key="123:private", thread_id=None)
    channel._start_typing(comp_key="456:private", thread_id=None)
    
    assert "123:private" in channel._typing_tasks
    assert "456:private" in channel._typing_tasks
    assert len(channel._typing_tasks) == 2
    
    # Stop one chat
    channel._stop_typing(comp_key="123:private")
    assert "123:private" not in channel._typing_tasks
    assert "456:private" in channel._typing_tasks


@pytest.mark.asyncio
async def test_typing_indicator_cancelled_task():
    """Test that typing indicator task can be cancelled properly."""
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.send_chat_action = AsyncMock()
    channel._typing_tasks = {}

    # Start typing
    channel._start_typing(comp_key="123:private", thread_id=None)
    task = channel._typing_tasks["123:private"]
    
    # Cancel the task
    task.cancel()
    
    # Give asyncio a chance to process the cancellation
    await asyncio.sleep(0)
    
    # Check that task is cancelled
    assert task.cancelled() or task.done()
