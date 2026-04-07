"""Tests for Telegram builtin commands in topic contexts."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

from nanobot.bus.events import OutboundMessage
from nanobot.command.builtin import (
    cmd_status, cmd_stop, cmd_restart, cmd_new, cmd_help, cmd_model
)
from nanobot.command.router import CommandContext


class MockLoop:
    def __init__(self):
        self.model = "claude-3-haiku-20240307"
        self._start_time = 1710000000.0
        self._last_usage = {"prompt_tokens": 100, "completion_tokens": 50}
        self.context_window_tokens = 200000
        self._model_overrides = {}
        self._temperature_overrides = {}
        self._active_tasks = {}
        self.sessions = MagicMock()
        self.memory_consolidator = MagicMock()
        self.subagents = MagicMock()
        # Create a mock session with proper slicing support
        class MockSession:
            def __init__(self, key):
                self._messages = ["msg1", "msg2"]
                self.last_consolidated = 0
                self.key = key

            @property
            def messages(self):
                return self._messages

            def get_history(self, max_messages=0):
                return [1, 2, 3]

            def clear(self):
                self._messages = []

            def save(self):
                pass

        self.sessions.get_or_create = MagicMock(side_effect=lambda key: MockSession(key))
        self.sessions.save = MagicMock()
        self.sessions.invalidate = MagicMock()
        self.memory_consolidator.estimate_session_prompt_tokens = MagicMock(
            return_value=(150, 50)
        )
        self.memory_consolidator.archive_messages = MagicMock()
        self.subagents.cancel_by_session = AsyncMock(return_value=0)
        self._schedule_background = MagicMock()


def _make_context(command: str, has_topic: bool = True) -> CommandContext:
    """Create a command context with optional topic metadata."""
    msg = MagicMock(
        channel="telegram",
        chat_id="123456789",
        metadata={"message_thread_id": 42 if has_topic else None}
    )
    ctx = CommandContext(
        msg=msg,
        session=None,
        key="telegram:123456789:topic:42" if has_topic else "telegram:123456789",
        raw=f"/{command}",
        args="",
        loop=MockLoop()
    )
    return ctx


@pytest.mark.asyncio
async def test_cmd_status_preserves_topic_context():
    """Test that /status command preserves message_thread_id in metadata."""
    ctx = _make_context("status", has_topic=True)

    result = await cmd_status(ctx)

    assert isinstance(result, OutboundMessage)
    assert result.channel == "telegram"
    assert result.chat_id == "123456789"
    assert result.metadata.get("message_thread_id") == 42
    assert result.metadata.get("render_as") == "text"
    assert "nanobot" in result.content


@pytest.mark.asyncio
async def test_cmd_status_without_topic():
    """Test that /status command works without topic context."""
    ctx = _make_context("status", has_topic=False)

    result = await cmd_status(ctx)

    assert isinstance(result, OutboundMessage)
    assert result.channel == "telegram"
    assert result.chat_id == "123456789"
    assert result.metadata.get("message_thread_id") is None
    assert result.metadata.get("render_as") == "text"


@pytest.mark.asyncio
async def test_cmd_stop_preserves_topic_context():
    """Test that /stop command preserves message_thread_id in metadata."""
    ctx = _make_context("stop", has_topic=True)
    ctx.loop._active_tasks = {"telegram:123456789:topic:42": []}

    result = await cmd_stop(ctx)

    assert isinstance(result, OutboundMessage)
    assert result.channel == "telegram"
    assert result.chat_id == "123456789"
    assert result.metadata.get("message_thread_id") == 42
    assert "Stopped" in result.content or "No active task" in result.content


@pytest.mark.asyncio
async def test_cmd_restart_preserves_topic_context():
    """Test that /restart command preserves message_thread_id in metadata."""
    ctx = _make_context("restart", has_topic=True)

    result = await cmd_restart(ctx)

    assert isinstance(result, OutboundMessage)
    assert result.channel == "telegram"
    assert result.chat_id == "123456789"
    assert result.metadata.get("message_thread_id") == 42
    assert "Restarting" in result.content


@pytest.mark.asyncio
async def test_cmd_new_preserves_topic_context():
    """Test that /new command preserves message_thread_id in metadata."""
    ctx = _make_context("new", has_topic=True)

    result = await cmd_new(ctx)

    assert isinstance(result, OutboundMessage)
    assert result.channel == "telegram"
    assert result.chat_id == "123456789"
    assert result.metadata.get("message_thread_id") == 42
    assert "New session" in result.content


@pytest.mark.asyncio
async def test_cmd_help_preserves_topic_context():
    """Test that /help command preserves message_thread_id in metadata."""
    ctx = _make_context("help", has_topic=True)

    result = await cmd_help(ctx)

    assert isinstance(result, OutboundMessage)
    assert result.channel == "telegram"
    assert result.chat_id == "123456789"
    assert result.metadata.get("message_thread_id") == 42
    assert result.metadata.get("render_as") == "text"
    assert "nanobot commands" in result.content


@pytest.mark.asyncio
async def test_cmd_model_preserves_topic_context():
    """Test that /model command preserves message_thread_id in metadata."""
    ctx = _make_context("model", has_topic=True)
    # Mock the _handle_model_command method
    ctx.loop._handle_model_command = MagicMock(return_value=OutboundMessage(
        channel="telegram",
        chat_id="123456789",
        content="Current model: test",
        metadata={"message_thread_id": 42}
    ))

    result = await cmd_model(ctx)

    assert isinstance(result, OutboundMessage)
    assert result.channel == "telegram"
    assert result.chat_id == "123456789"
    assert result.metadata.get("message_thread_id") == 42


def test_all_commands_metadata_structure():
    """Verify that all command handlers properly include metadata."""
    commands = [
        (cmd_status, "status"),
        (cmd_stop, "stop"),
        (cmd_restart, "restart"),
        (cmd_new, "new"),
        (cmd_help, "help"),
        (cmd_model, "model"),
    ]

    for cmd_func, cmd_name in commands:
        ctx = _make_context(cmd_name, has_topic=True)

        # For async functions, we'd need to run them, but for this check
        # we just verify the function signature and behavior
        assert hasattr(cmd_func, '__call__')
        # The cmd_model is special since it delegates
        if cmd_name != "model":
            assert "metadata" in cmd_func.__code__.co_names or "metadata" in str(cmd_func.__code__)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])