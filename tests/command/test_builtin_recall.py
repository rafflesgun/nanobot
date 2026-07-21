from __future__ import annotations

from types import SimpleNamespace

import pytest

from nanobot.bus.events import InboundMessage
from nanobot.command.builtin import cmd_recall
from nanobot.command.router import CommandContext


@pytest.mark.asyncio
async def test_recall_command_returns_text_metadata(tmp_path) -> None:
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "telegram_123.jsonl").write_text(
        '{"_type":"metadata","metadata":{},"key":"telegram:123"}\n'
        '{"role":"user","content":"Investigate retry loop","timestamp":"2026-04-22T09:01:00"}\n',
        encoding="utf-8",
    )

    msg = InboundMessage(
        channel="cli", sender_id="u1", chat_id="direct", content="/recall retry loop"
    )
    loop = SimpleNamespace(workspace=tmp_path)
    ctx = CommandContext(
        msg=msg, session=None, key=msg.session_key, raw=msg.content, args="retry loop", loop=loop
    )

    out = await cmd_recall(ctx)

    assert out.metadata["render_as"] == "text"
    assert "Session recall" in out.content


@pytest.mark.asyncio
async def test_recall_command_handles_missing_query(tmp_path) -> None:
    msg = InboundMessage(channel="cli", sender_id="u1", chat_id="direct", content="/recall")
    loop = SimpleNamespace(workspace=tmp_path)
    ctx = CommandContext(
        msg=msg, session=None, key=msg.session_key, raw=msg.content, args="", loop=loop
    )

    out = await cmd_recall(ctx)

    assert "Usage:" in out.content
