<<<<<<< HEAD
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
=======
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nanobot.agent.tools.image_generation import ImageGenerationTool
from nanobot.config.loader import set_config_path
from nanobot.config.schema import ImageGenerationToolConfig, ProviderConfig
from nanobot.providers.image_generation import GeneratedImageResponse

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x04\x00\x00\x00\xb5\x1c\x0c\x02"
    b"\x00\x00\x00\x0bIDATx\xdacd\xfc\xff\x1f\x00\x03\x03"
    b"\x02\x00\xef\xbf\xa7\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
)
PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


class FakeImageClient:
    instances: list["FakeImageClient"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.calls: list[dict[str, Any]] = []
        self.instances.append(self)

    async def generate(self, **kwargs: Any) -> GeneratedImageResponse:
        self.calls.append(kwargs)
        return GeneratedImageResponse(images=[PNG_DATA_URL], content="", raw={})


@pytest.mark.asyncio
async def test_generate_image_tool_stores_artifact_and_source_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_config_path(tmp_path / "config.json")
    FakeImageClient.instances = []
    monkeypatch.setattr(
        "nanobot.agent.tools.image_generation.get_image_gen_provider",
        lambda name: FakeImageClient if name == "openrouter" else None,
    )
    ref = tmp_path / "ref.png"
    ref.write_bytes(PNG_BYTES)
    tool = ImageGenerationTool(
        workspace=tmp_path,
        config=ImageGenerationToolConfig(enabled=True, max_images_per_turn=2),
        provider_config=ProviderConfig(api_key="sk-or-test"),
    )

    result = await tool.execute(
        prompt="make this blue",
        reference_images=["ref.png"],
        aspect_ratio="16:9",
        image_size="2K",
        count=2,
    )

    payload = json.loads(result)
    artifacts = payload["artifacts"]
    assert len(artifacts) == 2
    assert Path(artifacts[0]["path"]).is_file()
    assert artifacts[0]["source_images"] == [str(ref.resolve())]
    assert artifacts[0]["model"] == "openai/gpt-5.4-image-2"

    fake = FakeImageClient.instances[0]
    assert fake.kwargs["api_key"] == "sk-or-test"
    assert len(fake.calls) == 2
    assert fake.calls[0]["aspect_ratio"] == "16:9"
    assert fake.calls[0]["image_size"] == "2K"


@pytest.mark.asyncio
async def test_generate_image_tool_reports_missing_key(tmp_path: Path) -> None:
    tool = ImageGenerationTool(
        workspace=tmp_path,
        config=ImageGenerationToolConfig(enabled=True),
        provider_config=ProviderConfig(),
    )

    result = await tool.execute(prompt="draw")

    assert result.startswith("Error: OpenRouter API key is not configured")


@pytest.mark.asyncio
async def test_generate_image_tool_selects_aihubmix_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_config_path(tmp_path / "config.json")
    FakeImageClient.instances = []
    monkeypatch.setattr(
        "nanobot.agent.tools.image_generation.get_image_gen_provider",
        lambda name: FakeImageClient if name == "aihubmix" else None,
    )
    tool = ImageGenerationTool(
        workspace=tmp_path,
        config=ImageGenerationToolConfig(
            enabled=True,
            provider="aihubmix",
            model="gpt-image-2-free",
        ),
        provider_configs={
            "openrouter": ProviderConfig(api_key="sk-or-test"),
            "aihubmix": ProviderConfig(api_key="sk-ahm-test", extra_body={"quality": "low"}),
        },
    )

    result = await tool.execute(prompt="draw a poster", aspect_ratio="3:4")

    payload = json.loads(result)
    assert len(payload["artifacts"]) == 1
    fake = FakeImageClient.instances[0]
    assert fake.kwargs["api_key"] == "sk-ahm-test"
    assert fake.kwargs["extra_body"] == {"quality": "low"}
    assert fake.calls[0]["model"] == "gpt-image-2-free"
    assert fake.calls[0]["aspect_ratio"] == "3:4"


@pytest.mark.asyncio
async def test_generate_image_tool_reports_missing_aihubmix_key(tmp_path: Path) -> None:
    tool = ImageGenerationTool(
        workspace=tmp_path,
        config=ImageGenerationToolConfig(enabled=True, provider="aihubmix"),
        provider_configs={"aihubmix": ProviderConfig()},
    )

    result = await tool.execute(prompt="draw")

    assert result.startswith("Error: AIHubMix API key is not configured")


@pytest.mark.asyncio
async def test_generate_image_tool_allows_ollama_without_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_config_path(tmp_path / "config.json")
    FakeImageClient.instances = []
    monkeypatch.setattr(
        "nanobot.agent.tools.image_generation.get_image_gen_provider",
        lambda name: FakeImageClient if name == "ollama" else None,
    )
    tool = ImageGenerationTool(
        workspace=tmp_path,
        config=ImageGenerationToolConfig(
            enabled=True,
            provider="ollama",
            model="x/z-image-turbo",
        ),
        provider_configs={"ollama": ProviderConfig(api_base="http://localhost:11434/v1")},
    )

    result = await tool.execute(prompt="draw a cat")

    payload = json.loads(result)
    assert len(payload["artifacts"]) == 1

    fake = FakeImageClient.instances[0]
    assert fake.kwargs["api_key"] is None
    assert fake.kwargs["api_base"] == "http://localhost:11434/v1"
    assert fake.calls[0]["aspect_ratio"] == "1:1"
    assert fake.calls[0]["image_size"] == "1K"


@pytest.mark.asyncio
async def test_generate_image_tool_reports_missing_zhipu_key(tmp_path: Path) -> None:
    tool = ImageGenerationTool(
        workspace=tmp_path,
        config=ImageGenerationToolConfig(
            enabled=True,
            provider="zhipu",
            model="glm-image",
        ),
        provider_configs={"zhipu": ProviderConfig(api_base="https://open.bigmodel.cn/api/paas/v4")},
    )

    result = await tool.execute(prompt="draw a cat")

    assert result.startswith("Error: Zhipu API key is not configured")


@pytest.mark.asyncio
async def test_generate_image_tool_rejects_reference_outside_workspace(tmp_path: Path) -> None:
    set_config_path(tmp_path / "config.json")
    outside = tmp_path.parent / "outside.png"
    outside.write_bytes(PNG_BYTES)
    tool = ImageGenerationTool(
        workspace=tmp_path,
        config=ImageGenerationToolConfig(enabled=True),
        provider_config=ProviderConfig(api_key="sk-or-test"),
    )

    result = await tool.execute(prompt="edit", reference_images=[str(outside)])

    assert "reference_images must be inside the workspace" in result
>>>>>>> origin/main
