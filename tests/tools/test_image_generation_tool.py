import asyncio
from dataclasses import dataclass

import pytest

from nanobot.agent.tools.image_generation import GenerateImageTool
from nanobot.bus.events import OutboundMessage


@dataclass(frozen=True)
class _Result:
    path: str
    filename: str = "image.png"
    provider: str = "test"
    model: str = "test-model"


class _Service:
    def __init__(self, path: str = "/tmp/generated.png") -> None:
        self.path = path
        self.calls: list[tuple[str, str | None, str | None]] = []

    async def generate(
        self,
        prompt: str,
        n: int | None = None,
        size: str | None = None,
        quality: str | None = None,
    ) -> _Result:
        self.calls.append((prompt, n, size))
        return _Result(self.path)


class _FailingService:
    async def generate(
        self,
        prompt: str,
        n: int | None = None,
        size: str | None = None,
        quality: str | None = None,
    ) -> _Result:
        msg = "OpenAI API error: 500 Internal Server Error"
        raise RuntimeError(msg)


@pytest.mark.asyncio
async def test_generate_image_reports_generation_failure_without_exception_details() -> None:
    async def _send(_msg: OutboundMessage) -> None:
        return None

    tool = GenerateImageTool(_FailingService())
    tool.set_send_callback(_send)
    tool.set_context("telegram", "chat-1")

    result = await tool.execute("draw a robot")

    assert result == "Error: Image generation failed."
    assert "/Users/raffles" not in result
    assert "base64" not in result.lower()
    assert "provider" not in result.lower()
    assert "openai" not in result.lower()


@pytest.mark.asyncio
async def test_generate_image_context_is_task_local_under_asyncio_gather() -> None:
    service = _Service()
    sent: list[OutboundMessage] = []

    async def _send(msg: OutboundMessage) -> None:
        sent.append(msg)

    tool = GenerateImageTool(service)
    tool.set_send_callback(_send)

    async def _run(channel: str, chat_id: str, prompt: str) -> str:
        tool.set_context(channel, chat_id, message_id=f"msg-{chat_id}")
        await asyncio.sleep(0)
        return await tool.execute(prompt)

    results = await asyncio.gather(
        _run("telegram", "chat-1", "one"),
        _run("discord", "chat-2", "two"),
    )

    assert results == ["Image generated and sent.", "Image generated and sent."]
    assert [(msg.channel, msg.chat_id, msg.metadata) for msg in sent] == [
        ("telegram", "chat-1", {"message_id": "msg-chat-1"}),
        ("discord", "chat-2", {"message_id": "msg-chat-2"}),
    ]
