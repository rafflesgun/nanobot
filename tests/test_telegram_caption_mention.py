import asyncio
from types import SimpleNamespace

import pytest

from nanobot.bus.queue import MessageBus
from nanobot.channels.telegram.runtime import TelegramChannel
from nanobot.config.schema import TelegramConfig


@pytest.mark.asyncio
async def test_on_message_accepts_mention_in_caption(monkeypatch) -> None:
    # Setup channel with mention-only policy
    cfg = TelegramConfig(enabled=True, group_policy="mention", allow_from=["*"])
    bus = MessageBus()
    channel = TelegramChannel(cfg, bus)

    # Fake app.bot.get_me() to return bot info
    class _FakeBot:
        async def get_me(self):
            return SimpleNamespace(username="botname", id=123)

        async def set_message_reaction(self, *args, **kwargs):
            return None

        async def send_chat_action(self, *args, **kwargs):
            return None

    channel._app = SimpleNamespace(bot=_FakeBot())

    # Prevent typing loop from creating background tasks
    monkeypatch.setattr(channel, "_start_typing", lambda *a, **k: None)

    # Capture forwarded messages instead of publishing to bus
    handled = []

    async def _fake_handle_message(sender_id, chat_id, content, **kwargs):
        handled.append((sender_id, chat_id, content))

    channel._handle_message = _fake_handle_message  # type: ignore[assignment]

    # Build fake update where mention is in caption (media message)
    mention_text = "@botname"
    entity = SimpleNamespace(type="mention", offset=0, length=len(mention_text))
    message = SimpleNamespace(
        chat=SimpleNamespace(type="group"),
        chat_id=-100123,
        entities=None,
        caption_entities=[entity],
        text=None,
        caption=mention_text + " hello",
        reply_to_message=None,
        message_id=55,
        photo=None,
        voice=None,
        audio=None,
        document=None,
        media_group_id=None,
        message_thread_id=None,
    )

    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=111, username="alice", first_name="Alice"))

    await channel._on_message(update, None)
    await asyncio.sleep(0.12)

    assert handled, "_handle_message was not called"
    assert handled[0][0].startswith("111"), "sender_id should be derived from effective_user"
