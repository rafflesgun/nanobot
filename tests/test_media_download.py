"""Tests for media download saving to workspace/media/."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from nanobot.channels.telegram.runtime import TelegramChannel


@pytest.mark.asyncio
async def test_media_saved_in_workspace():
    workspace = Path("/tmp/test_workspace")
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    config.react_emoji = "👀"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._workspace_path = workspace
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.get_file = AsyncMock()

    file_obj = AsyncMock()
    channel._app.bot.get_file.return_value = file_obj
    file_obj.download_to_drive = AsyncMock()

    photo = AsyncMock(file_id="abc123")
    message = AsyncMock(photo=[photo])
    message.chat_id = 123456
    message.chat.type = "private"
    message.text = None
    message.caption = None
    message.message_thread_id = None
    message.text = None
    message.caption = None
    message.message_thread_id = None

    update = AsyncMock()
    update.message = message
    update.effective_user = AsyncMock(id=123, username="testuser", first_name="Test")

    context = AsyncMock()

    with patch.object(channel, '_get_extension', return_value=".jpg"):
        # Patch the mkdir method to prevent actual filesystem operations
        with patch('pathlib.Path.mkdir'):
            await channel._on_message(update, context)

    assert channel._app.bot.get_file.called
    assert file_obj.download_to_drive.called


@pytest.mark.asyncio
async def test_media_fallback_to_home():
    config = AsyncMock()
    config.group_policy = "mention"
    config.token = "fake_token"
    config.react_emoji = "👀"
    bus = AsyncMock()
    channel = TelegramChannel(config=config, bus=bus)
    channel._workspace_path = None
    channel._app = AsyncMock()
    channel._app.bot = AsyncMock()
    channel._app.bot.get_file = AsyncMock()

    file_obj = AsyncMock()
    channel._app.bot.get_file.return_value = file_obj
    file_obj.download_to_drive = AsyncMock()

    photo = AsyncMock(file_id="abc123")
    message = AsyncMock(photo=[photo])
    message.chat_id = 123456
    message.chat.type = "private"
    message.text = "Test message with photo"

    update = AsyncMock()
    update.message = message
    update.effective_user = AsyncMock(id=123, username="testuser", first_name="Test")

    context = AsyncMock()

    with patch.object(channel, '_get_extension', return_value=".jpg"):
        # Same Path patch
        with patch('pathlib.Path.mkdir'):
            await channel._on_message(update, context)

    assert file_obj.download_to_drive.called
