"""Tests for AgentLoop /stats output formatting."""

from unittest.mock import MagicMock, patch

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.bus.events import InboundMessage


def _make_loop(tmp_path):
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    with patch("nanobot.agent.loop.ContextBuilder"), \
         patch("nanobot.agent.loop.SessionManager"), \
         patch("nanobot.agent.loop.SubagentManager"):
        return AgentLoop(bus=MessageBus(), provider=provider, workspace=tmp_path)


def _message() -> InboundMessage:
    return InboundMessage(
        channel="cli",
        sender_id="user-1",
        chat_id="chat-1",
        content="/stats",
        metadata={},
    )


@pytest.mark.asyncio
async def test_stats_command_shows_cached_tokens_for_chat(tmp_path):
    loop = _make_loop(tmp_path)
    loop.stats_manager.record_usage(
        "cli",
        "chat-1",
        "test-model",
        input_tokens=200,
        output_tokens=50,
        total_tokens=250,
        session_key="session-1",
        cached_tokens=120,
    )

    response = await loop._handle_stats_command(_message(), [])

    assert "• Cached tokens: 120" in response.content
    assert "• Cache hit rate: 60%" in response.content


@pytest.mark.asyncio
async def test_stats_all_shows_cached_tokens_by_channel(tmp_path):
    loop = _make_loop(tmp_path)
    loop.stats_manager.record_usage(
        "cli",
        "chat-1",
        "test-model",
        input_tokens=200,
        output_tokens=50,
        total_tokens=250,
        session_key="session-1",
        cached_tokens=120,
    )

    response = await loop._handle_stats_command(_message(), ["all"])

    assert "• Cached tokens: 120" in response.content
    assert "• Cache hit rate: 60%" in response.content
    assert "📡 cli: 250 tokens, 120 cached (1 messages)" in response.content
