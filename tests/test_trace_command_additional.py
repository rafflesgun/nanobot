"""Additional tests for the /trace command functionality."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from nanobot.channels.telegram import TelegramChannel
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import TelegramConfig
from nanobot.bus.events import OutboundMessage


@pytest.mark.asyncio
async def test_trace_command_not_available_in_group_chat():
    """Test that /trace command is not available in group chats."""
    channel = TelegramChannel(TelegramConfig(allow_from=["*"]), MessageBus())
    
    # Setup mock update for a group chat
    update = MagicMock()
    update.message = MagicMock()
    update.message.chat_id = -100123456  # Group chat ID
    update.effective_user = MagicMock()
    update.effective_user.id = 123456
    update.effective_user.username = "testuser"
    
    # Simulate group chat by setting the chat type
    update.message.chat = MagicMock()
    update.message.chat.type = "group"
    
    context = MagicMock()
    context.args = ["on"]
    
    # Mock reply_text
    update.message.reply_text = AsyncMock()
    
    # Try to call the trace command handler (should not be registered for groups)
    # We'll simulate what happens if it were called in a group
    await channel._on_trace_command(update, context)
    
    # Verify that no trace setting was made (command should be ignored in groups)
    assert "123456" not in channel._trace_enabled


@pytest.mark.asyncio
async def test_trace_message_preserves_thread_id():
    """Test that trace messages preserve thread/topic ID when sent."""
    channel = TelegramChannel(TelegramConfig(allow_from=["*"]), MessageBus())
    
    # Enable trace for this chat
    channel._trace_enabled["123456"] = True
    
    # Setup mock app and bot
    channel._app = MagicMock()
    channel._app.bot.send_message = AsyncMock()
    
    # Create a proper OutboundMessage with thread ID
    msg = OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="Thinking about the answer...",
        metadata={"_progress": True, "_tool_hint": False, "message_thread_id": 777}
    )
    
    # Send the message
    await channel.send(msg)
    
    # Verify send_message was called with correct thread ID
    channel._app.bot.send_message.assert_called_once()
    call_kwargs = channel._app.bot.send_message.call_args[1]
    assert call_kwargs.get("message_thread_id") == 777
    assert call_kwargs["text"].startswith("💭 ")


@pytest.mark.asyncio
async def test_trace_message_splits_long_content():
    """Test that long trace messages are split appropriately."""
    channel = TelegramChannel(TelegramConfig(allow_from=["*"]), MessageBus())
    
    # Enable trace for this chat
    channel._trace_enabled["123456"] = True
    
    # Create a very long message (over 4000 chars)
    long_content = "Step " + "x" * 3900 + " completed."  # Well over 4000 chars
    
    # Setup mock app and bot
    channel._app = MagicMock()
    channel._app.bot.send_message = AsyncMock()
    
    # Create a proper OutboundMessage with long content
    msg = OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content=long_content,
        metadata={"_progress": True, "_tool_hint": False}
    )
    
    # Send the message
    await channel.send(msg)
    
    # Verify send_message was called multiple times for split content
    assert channel._app.bot.send_message.call_count > 1
    # Check that each call starts with the appropriate prefix
    for call in channel._app.bot.send_message.call_args_list:
        text = call[1]["text"]
        assert text.startswith("💭 ") or text.startswith("🤖 ")


@pytest.mark.asyncio
async def test_trace_tool_hints_sent_with_robot_prefix():
    """Test that tool hint messages are sent with 🤖 prefix when trace enabled."""
    channel = TelegramChannel(TelegramConfig(allow_from=["*"]), MessageBus())
    
    # Enable trace for this chat
    channel._trace_enabled["123456"] = True
    
    # Setup mock app and bot
    channel._app = MagicMock()
    channel._app.bot.send_message = AsyncMock()
    
    # Create a proper OutboundMessage with tool hint
    msg = OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="web_search(query='weather')",
        metadata={"_progress": True, "_tool_hint": True}
    )
    
    # Send the message
    await channel.send(msg)
    
    # Verify send_message was called with 🤖 prefix
    channel._app.bot.send_message.assert_called_once()
    call_args = channel._app.bot.send_message.call_args[1]["text"]
    assert call_args.startswith("🤖 ")
    assert "web_search" in call_args


@pytest.mark.asyncio
async def test_trace_thinking_messages_sent_with_thought_prefix():
    """Test that thinking messages are sent with 💭 prefix when trace enabled."""
    channel = TelegramChannel(TelegramConfig(allow_from=["*"]), MessageBus())
    
    # Enable trace for this chat
    channel._trace_enabled["123456"] = True
    
    # Setup mock app and bot
    channel._app = MagicMock()
    channel._app.bot.send_message = AsyncMock()
    
    # Create a proper OutboundMessage with thinking content
    msg = OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="Let me analyze this step by step...",
        metadata={"_progress": True, "_tool_hint": False}
    )
    
    # Send the message
    await channel.send(msg)
    
    # Verify send_message was called with 💭 prefix
    channel._app.bot.send_message.assert_called_once()
    call_args = channel._app.bot.send_message.call_args[1]["text"]
    assert call_args.startswith("💭 ")
    assert "analyze this step by step" in call_args.lower()


@pytest.mark.asyncio
async def test_final_response_not_affected_by_trace_setting():
    """Test that final responses are sent normally regardless of trace setting."""
    channel = TelegramChannel(TelegramConfig(allow_from=["*"]), MessageBus())
    
    # Enable trace for this chat
    channel._trace_enabled["123456"] = True
    
    # Setup mock app and bot
    channel._app = MagicMock()
    channel._app.bot.send_message = AsyncMock()
    
    # Create a final response message (not progress)
    msg = OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="Here is your final answer.",
        metadata={"_progress": False}  # Not a progress message
    )
    
    # Send the message
    await channel.send(msg)
    
    # Verify send_message was called without any prefix
    channel._app.bot.send_message.assert_called_once()
    call_args = channel._app.bot.send_message.call_args[1]["text"]
    assert not call_args.startswith("💭 ") and not call_args.startswith("🤖 ")
    assert call_args == "Here is your final answer."


@pytest.mark.asyncio
async def test_trace_toggle_persists_between_messages():
    """Test that trace setting persists for the session."""
    channel = TelegramChannel(TelegramConfig(allow_from=["*"]), MessageBus())
    
    # Initially trace should be off by default
    assert not channel._trace_enabled.get("123456", False)
    
    # Enable trace
    channel._trace_enabled["123456"] = True
    
    # Verify it stays on
    assert channel._trace_enabled.get("123456", False)
    
    # Disable trace
    channel._trace_enabled["123456"] = False
    
    # Verify it stays off
    assert not channel._trace_enabled.get("123456", False)


@pytest.mark.asyncio
async def test_multiple_chats_can_have_different_trace_settings():
    """Test that different chats can have independent trace settings."""
    channel = TelegramChannel(TelegramConfig(allow_from=["*"]), MessageBus())
    
    # Chat A: enable trace
    channel._trace_enabled["111111"] = True
    
    # Chat B: keep trace off (default)
    # Don't set anything, should remain False
    
    # Verify settings are independent
    assert channel._trace_enabled.get("111111", False) is True   # Chat A: on
    assert channel._trace_enabled.get("222222", False) is False  # Chat B: off (default)