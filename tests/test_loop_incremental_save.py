"""Tests for incremental/checkpoint-based session saving in agent loops.

The ``on_turn_saved`` callback was removed upstream in favor of the
checkpoint-based persistence mechanism in ``AgentLoop``.  The runner now
emits checkpoints via ``_set_runtime_checkpoint`` after tool calls.

These tests verify:
- Sessions are persisted for non-ephemeral runs
- Ephemeral runs skip session persistence
- The checkpoint/restore cycle recovers mid-turn state
"""

from pathlib import Path

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.session.manager import Session, SessionManager


class ScriptedProvider(LLMProvider):
    def __init__(self, responses):
        super().__init__()
        self._responses = list(responses)
        self.calls = 0
        self.last_kwargs: dict = {}

    async def chat(self, *args, **kwargs) -> LLMResponse:
        self.calls += 1
        self.last_kwargs = kwargs
        response = self._responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if isinstance(response, dict):
            response_dict = response.copy()
            response_dict.pop("role", None)
            return LLMResponse(**response_dict)
        return response

    def get_default_model(self) -> str:
        return "test-model"


@pytest.mark.asyncio
async def test_process_direct_persists_session(tmp_path: Path):
    """Non-ephemeral process_direct persists the session to disk."""
    bus = MessageBus()
    provider = ScriptedProvider(responses=[
        {"content": "Response", "finish_reason": "stop"},
    ])

    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        session_manager=SessionManager(tmp_path),
    )

    result = await loop.process_direct(
        content="Test message",
        session_key="test-session",
    )

    assert result is not None
    assert "Response" in (result.content or "")
    session_path = loop.sessions._get_session_path("test-session")
    assert session_path.exists()


@pytest.mark.asyncio
async def test_ephemeral_process_direct_skips_persistence(tmp_path: Path):
    """Ephemeral process_direct does NOT persist session data."""
    bus = MessageBus()
    provider = ScriptedProvider(responses=[
        {"content": "Response", "finish_reason": "stop"},
    ])

    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        session_manager=SessionManager(tmp_path),
    )

    result = await loop.process_direct(
        content="Test message",
        session_key="ephemeral-test",
        ephemeral=True,
    )

    assert result is not None
    assert "Response" in (result.content or "")
    session_path = loop.sessions._get_session_path("ephemeral-test")
    assert not session_path.exists()


@pytest.mark.asyncio
async def test_checkpoint_save_load_roundtrip(tmp_path: Path):
    """_set_runtime_checkpoint persists to disk; _restore_runtime_checkpoint recovers it."""
    bus = MessageBus()
    provider = ScriptedProvider(responses=[
        {"content": "Hello", "finish_reason": "stop"},
    ])

    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        session_manager=SessionManager(tmp_path),
    )
    session = loop.sessions.get_or_create("restore-test")

    checkpoint_payload = {
        "assistant_message": {
            "role": "assistant",
            "content": "Let me check that.",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path": "test.txt"}'},
                }
            ],
        },
        "completed_tool_results": [],
        "pending_tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "read_file", "arguments": '{"path": "test.txt"}'},
            }
        ],
    }

    loop._set_runtime_checkpoint(session, checkpoint_payload)
    assert "runtime_checkpoint" in session.metadata

    # Reload from disk — checkpoint metadata must survive
    session2 = loop.sessions._load("restore-test")
    assert session2 is not None
    assert "runtime_checkpoint" in session2.metadata

    # Restore rehydrates messages and clears checkpoint
    restored = loop._restore_runtime_checkpoint(session2)
    assert restored is True
    assert len(session2.messages) > 0
    assert "runtime_checkpoint" not in session2.metadata


@pytest.mark.asyncio
async def test_ephemeral_checkpoint_is_not_persisted(tmp_path: Path):
    """_set_runtime_checkpoint silently no-ops for ephemeral sessions."""
    session = Session(key="ephemeral-test")
    session.metadata["_ephemeral"] = True

    bus = MessageBus()
    provider = ScriptedProvider(responses=[])
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        session_manager=SessionManager(tmp_path),
    )

    loop._set_runtime_checkpoint(session, {"key": "should-not-persist"})
    assert "runtime_checkpoint" not in session.metadata


@pytest.mark.asyncio
async def test_results_survive_across_multiple_turns(tmp_path: Path):
    """Turns on the same session accumulate; earlier results are not lost."""
    bus = MessageBus()
    provider = ScriptedProvider(responses=[
        {"content": "First response", "finish_reason": "stop"},
        {"content": "Second response", "finish_reason": "stop"},
    ])

    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        session_manager=SessionManager(tmp_path),
    )

    await loop.process_direct(content="Message 1", session_key="multi-turn")
    await loop.process_direct(content="Message 2", session_key="multi-turn")

    session = loop.sessions._load("multi-turn")
    assert session is not None
    # Both turns should be in the history
    user_msgs = [m for m in session.messages if m["role"] == "user"]
    asst_msgs = [m for m in session.messages if m["role"] == "assistant"]
    assert len(user_msgs) >= 2
    assert len(asst_msgs) >= 2
