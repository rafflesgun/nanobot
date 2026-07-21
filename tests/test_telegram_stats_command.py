"""Tests for Telegram /stats command functionality."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from nanobot.bus.queue import MessageBus
from nanobot.channels.telegram.runtime import TelegramChannel
from nanobot.config.schema import TelegramConfig


class _FakeApp:
    def __init__(self) -> None:
        self.bot = SimpleNamespace()
        self.handlers = []
        self.error_handlers = []

    def add_error_handler(self, handler) -> None:
        self.error_handlers.append(handler)

    def add_handler(self, handler) -> None:
        self.handlers.append(handler)

    async def initialize(self) -> None:
        pass

    async def start(self) -> None:
        pass


def _make_telegram_update(*, text: str = None, args: list = None):
    """Create a fake Telegram update for testing."""
    user = SimpleNamespace(id=12345, username="test_user", first_name="Test")
    message = SimpleNamespace(
        chat=SimpleNamespace(type="private"),
        chat_id=123456789,
        text=text,
        message_id=1,
    )
    return SimpleNamespace(
        message=message,
        effective_user=user,
        effective_message=message,
    ), SimpleNamespace(args=args if args else [])


@pytest.mark.asyncio
async def test_stats_command_no_stats_file(tmp_path):
    """Test /stats command when no stats file exists."""
    config = TelegramConfig(enabled=True, token="123:abc", allow_from=["*"])
    channel = TelegramChannel(config, MessageBus())
    channel._app = _FakeApp()
    channel._workspace_path = str(tmp_path)

    update, context = _make_telegram_update(text="/stats")

    # Mock the reply_text method
    update.message.reply_text = AsyncMock()

    await channel._on_stats_command(update, context)

    # Should show "No token usage statistics found for this chat"
    update.message.reply_text.assert_called_once_with(
        "📊 No token usage statistics found for this chat.", parse_mode="HTML"
    )


@pytest.mark.asyncio
async def test_stats_command_with_data(tmp_path):
    """Test /stats command when stats data exists."""
    config = TelegramConfig(enabled=True, token="123:abc", allow_from=["*"])
    channel = TelegramChannel(config, MessageBus())
    channel._app = _FakeApp()
    channel._workspace_path = str(tmp_path)

    # Create stats data
    stats_dir = tmp_path / "stats"
    stats_dir.mkdir()
    usage_file = stats_dir / "usage.jsonl"

    # Add some Telegram stats data
    stats_data = [
        {
            "timestamp": "2024-01-01T00:00:00",
            "channel": "telegram",
            "chat_id": "123456789",
            "model": "claude-3-opus-20240229",
            "input_tokens": 150,
            "output_tokens": 100,
            "total_tokens": 250,
            "session_key": "test_session"
        },
        {
            "timestamp": "2024-01-02T00:00:00",
            "channel": "telegram",
            "chat_id": "123456789",
            "model": "claude-3-opus-20240229",
            "input_tokens": 200,
            "output_tokens": 150,
            "total_tokens": 350,
            "session_key": "test_session"
        }
    ]

    with open(usage_file, "w") as f:
        for data in stats_data:
            f.write(json.dumps(data) + "\n")

    update, context = _make_telegram_update(text="/stats")

    # Mock the reply_text method
    update.message.reply_text = AsyncMock()

    await channel._on_stats_command(update, context)

    # Should show formatted stats
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "Token Usage Statistics (This Chat)" in call_args
    assert "2" in call_args


@pytest.mark.asyncio
async def test_stats_command_all(tmp_path):
    """Test /stats all command."""
    config = TelegramConfig(enabled=True, token="123:abc", allow_from=["*"])
    channel = TelegramChannel(config, MessageBus())
    channel._app = _FakeApp()
    channel._workspace_path = str(tmp_path)

    # Create stats data with multiple channels
    stats_dir = tmp_path / "stats"
    stats_dir.mkdir()
    usage_file = stats_dir / "usage.jsonl"

    stats_data = [
        {
            "timestamp": "2024-01-01T00:00:00",
            "channel": "telegram",
            "chat_id": "123456789",
            "model": "claude-3-opus-20240229",
            "input_tokens": 150,
            "output_tokens": 100,
            "total_tokens": 250,
            "session_key": "test_session"
        },
        {
            "timestamp": "2024-01-02T00:00:00",
            "channel": "slack",
            "chat_id": "C123456",
            "model": "claude-3-opus-20240229",
            "input_tokens": 300,
            "output_tokens": 200,
            "total_tokens": 500,
            "session_key": "test_session"
        }
    ]

    with open(usage_file, "w") as f:
        for data in stats_data:
            f.write(json.dumps(data) + "\n")

    update, context = _make_telegram_update(text="/stats", args=["all"])

    # Mock the reply_text method
    update.message.reply_text = AsyncMock()

    await channel._on_stats_command(update, context)

    # Should show total stats across all channels
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "Total Token Usage Statistics" in call_args
    assert "2" in call_args


@pytest.mark.asyncio
async def test_stats_command_unauthorized():
    """Test /stats command when user is not authorized."""
    config = TelegramConfig(enabled=True, token="123:abc", allow_from=["allowed_user"])
    channel = TelegramChannel(config, MessageBus())
    channel._app = _FakeApp()

    update, context = _make_telegram_update(text="/stats")

    # Mock the reply_text method
    update.message.reply_text = AsyncMock()

    await channel._on_stats_command(update, context)

    # Should show authorization error
    update.message.reply_text.assert_called_once_with(
        "❌ You are not authorized to use this bot."
    )


@pytest.mark.asyncio
async def test_stats_command_error_handling(tmp_path):
    """Test /stats command error handling."""
    config = TelegramConfig(enabled=True, token="123:abc", allow_from=["*"])
    channel = TelegramChannel(config, MessageBus())
    channel._app = _FakeApp()
    channel._workspace_path = str(tmp_path)

    # Create a corrupted stats file
    stats_dir = tmp_path / "stats"
    stats_dir.mkdir()
    usage_file = stats_dir / "usage.jsonl"

    with open(usage_file, "w") as f:
        f.write("invalid json data\n")

    update, context = _make_telegram_update(text="/stats")

    # Mock the reply_text method
    update.message.reply_text = AsyncMock()

    await channel._on_stats_command(update, context)

    # StatsManager handles corrupted files internally by returning empty stats,
    # so the command shows "no stats" rather than an error
    update.message.reply_text.assert_called_once_with(
        "📊 No token usage statistics found for this chat.", parse_mode="HTML"
    )


@pytest.mark.asyncio
async def test_stats_command_topic_no_topic(tmp_path):
    """Test /stats topic command when not in a topic thread."""
    config = TelegramConfig(enabled=True, token="123:abc", allow_from=["*"])
    channel = TelegramChannel(config, MessageBus())
    channel._app = _FakeApp()
    channel._workspace_path = str(tmp_path)

    update, context = _make_telegram_update(text="/stats", args=["topic"])

    # Mock the reply_text method
    update.message.reply_text = AsyncMock()

    await channel._on_stats_command(update, context)

    # Should show error message for non-topic context
    update.message.reply_text.assert_called_once_with(
        "❌ This command is only available in topic threads.", parse_mode="HTML"
    )
