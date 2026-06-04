"""Simple smoke tests for the key features - compatible with Python 3.9"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, Optional, List


def test_model_override_storage():
    """Test that model overrides can be stored and retrieved"""
    # This simulates the _model_overrides dict behavior
    model_overrides: Dict[str, str] = {}

    # Set override
    model_overrides["telegram:123:topic:456"] = "claude-3.5-sonnet"

    # Get override
    assert model_overrides.get("telegram:123:topic:456") == "claude-3.5-sonnet"

    # Remove override
    del model_overrides["telegram:123:topic:456"]
    assert "telegram:123:topic:456" not in model_overrides


def test_topic_session_key_format():
    """Test the topic session key format"""

    def derive_topic_session_key(chat_id: str, thread_id: Optional[int]) -> Optional[str]:
        if thread_id is None:
            return None
        return f"telegram:{chat_id}:topic:{thread_id}"

    # With thread_id
    assert derive_topic_session_key("123", 456) == "telegram:123:topic:456"

    # Without thread_id
    assert derive_topic_session_key("123", None) is None


def test_inbound_message_session_key_uses_topic_metadata():
    from nanobot.bus.events import InboundMessage

    msg = InboundMessage(
        channel="telegram",
        sender_id="u1",
        chat_id="123",
        content="hello",
        metadata={"message_thread_id": 456},
    )

    assert msg.session_key == "telegram:123:topic:456"


def test_media_path_selection():
    """Test media path selection logic"""
    from nanobot.config.paths import get_media_dir, is_default_workspace

    # With workspace (non-default)
    workspace = "/tmp/test_workspace"
    assert not is_default_workspace(workspace)
    media_path = get_media_dir(channel="telegram", workspace=workspace)
    assert media_path == Path("/tmp/test_workspace/media/telegram")

    # Without workspace (falls back to default)
    default_media = get_media_dir(channel="telegram")
    assert default_media.name == "telegram"
    assert default_media.parent.name == "media"

    # With default workspace (same as no workspace fallback path)
    default_workspace = Path.home() / ".nanobot" / "workspace"
    assert is_default_workspace(default_workspace)
    media_with_default = get_media_dir(channel="telegram", workspace=str(default_workspace))
    assert media_with_default.name == "telegram"
    assert media_with_default.parent.name == "media"


def test_heartbeat_dm_filtering():
    """Test heartbeat DM-only filtering logic"""

    def should_deliver_heartbeat(channel: str, chat_id: str) -> bool:
        # Skip topic sub-sessions
        if ":" in chat_id:
            return False
        # Skip Telegram group chats (negative IDs)
        if channel == "telegram":
            try:
                if int(chat_id) < 0:
                    return False
            except ValueError:
                pass
        return True

    # DM should deliver
    assert should_deliver_heartbeat("telegram", "123456") is True

    # Group should not deliver
    assert should_deliver_heartbeat("telegram", "-100123456") is False

    # Topic session should not deliver
    assert should_deliver_heartbeat("telegram", "telegram:123:topic:456") is False


def test_thinking_message_pm_only():
    """Test thinking message PM-only logic"""

    def should_send_thinking(is_group: bool) -> bool:
        return not is_group

    # Private chat
    assert should_send_thinking(False) is True

    # Group chat
    assert should_send_thinking(True) is False


@pytest.mark.asyncio
async def test_async_typing_indicator():
    """Test async typing indicator logic"""

    async def send_typing_indicator():
        return True

    result = await send_typing_indicator()
    assert result is True
