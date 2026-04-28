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
        *,
        size: str | None = None,
        quality: str | None = None,
    ) -> _Result:
        self.calls.append((prompt, size, quality))
        return _Result(self.path)


class _FailingService:
    async def generate(
        self,
        prompt: str,
        *,
        size: str | None = None,
        quality: str | None = None,
    ) -> _Result:
        raise RuntimeError(
            "openai provider failed writing /Users/raffles/.cache/base64-secret.png"
        )


@pytest.mark.asyncio
async def test_generate_image_auto_sends_media_to_current_chat_and_forwards_overrides() -> None:
    service = _Service("/tmp/one.png")
    sent: list[OutboundMessage] = []

    async def _send(msg: OutboundMessage) -> None:
        sent.append(msg)

    tool = GenerateImageTool(service)
    tool.set_send_callback(_send)
    tool.set_context(
        "telegram",
        "chat-1",
        message_id="msg-1",
        thread_id=42,
        metadata={"existing": "value"},
    )

    result = await tool.execute("draw a robot", size="1024x1024", quality="high")

    assert result == "Image generated and sent."
    assert service.calls == [("draw a robot", "1024x1024", "high")]
    assert sent == [
        OutboundMessage(
            channel="telegram",
            chat_id="chat-1",
            content="Generated image",
            media=["/tmp/one.png"],
            metadata={
                "existing": "value",
                "message_id": "msg-1",
                "message_thread_id": 42,
            },
        )
    ]


@pytest.mark.asyncio
async def test_generate_image_returns_no_target_context_error() -> None:
    tool = GenerateImageTool(_Service())
    tool.set_send_callback(lambda _msg: asyncio.sleep(0))

    result = await tool.execute("draw a robot")

    assert result == "Error: No target channel/chat specified"


@pytest.mark.asyncio
async def test_generate_image_result_stays_compact_and_excludes_path_and_provider_details() -> None:
    service = _Service("/tmp/secret-generated.png")

    async def _send(_msg: OutboundMessage) -> None:
        return None

    tool = GenerateImageTool(service)
    tool.set_send_callback(_send)
    tool.set_context("telegram", "chat-1")

    result = await tool.execute("draw a robot")

    assert result == "Image generated and sent."
    assert "/tmp/secret-generated.png" not in result
    assert "base64" not in result.lower()
    assert "provider" not in result.lower()
    assert "test-model" not in result


@pytest.mark.asyncio
async def test_generate_image_reports_send_failure_after_generation_succeeds() -> None:
    service = _Service("/tmp/generated.png")

    async def _send(_msg: OutboundMessage) -> None:
        raise RuntimeError("telegram provider rejected /tmp/generated.png base64 payload")

    tool = GenerateImageTool(service)
    tool.set_send_callback(_send)
    tool.set_context("telegram", "chat-1")

    result = await tool.execute("draw a robot")

    assert service.calls == [("draw a robot", None, None)]
    assert result == "Image generated but failed to send."
    assert "/tmp/generated.png" not in result
    assert "base64" not in result.lower()
    assert "provider" not in result.lower()


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
