from __future__ import annotations

import base64
from types import SimpleNamespace

import pytest

from nanobot.image_generation import ImageGenerationService


class _FakeImages:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def generate(self, **kwargs):
        self.calls.append(kwargs)
        png_bytes = b"\x89PNG\r\n\x1a\nfake"
        return SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(png_bytes).decode("ascii"))]
        )


class _FakeClient:
    def __init__(self) -> None:
        self.images = _FakeImages()


@pytest.mark.asyncio
async def test_service_generates_and_saves_png(tmp_path) -> None:
    client = _FakeClient()
    service = ImageGenerationService(
        api_key="key",
        model="gpt-image-1",
        size="1024x1024",
        quality="auto",
        workspace=tmp_path,
        client=client,
    )

    result = await service.generate("a small robot")

    assert result.path.endswith(".png")
    assert result.filename.endswith(".png")
    assert result.model == "gpt-image-1"
    assert result.provider == "openai"
    assert (tmp_path / "media" / "generated" / result.filename).read_bytes().startswith(b"\x89PNG")
    assert "base64" not in str(result)

    assert client.images.calls == [
        {
            "model": "gpt-image-1",
            "prompt": "a small robot",
            "size": "1024x1024",
            "quality": "auto",
            "n": 1,
        }
    ]


@pytest.mark.asyncio
async def test_service_allows_per_call_overrides(tmp_path) -> None:
    client = _FakeClient()
    service = ImageGenerationService(
        api_key="key",
        model="gpt-image-1",
        size="1024x1024",
        quality="auto",
        workspace=tmp_path,
        client=client,
    )

    await service.generate("wide landscape", size="1536x1024", quality="high")

    assert client.images.calls[0]["size"] == "1536x1024"
    assert client.images.calls[0]["quality"] == "high"


@pytest.mark.asyncio
async def test_service_requests_base64_response_for_dall_e_models(tmp_path) -> None:
    client = _FakeClient()
    service = ImageGenerationService(
        api_key="key",
        model="dall-e-3",
        size="1024x1024",
        quality="auto",
        workspace=tmp_path,
        client=client,
    )

    await service.generate("a painted robot")

    assert client.images.calls[0]["response_format"] == "b64_json"


@pytest.mark.asyncio
async def test_service_errors_on_empty_image_response(tmp_path) -> None:
    class _EmptyImages:
        async def generate(self, **kwargs):
            return SimpleNamespace(data=[])

    class _EmptyClient:
        images = _EmptyImages()

    service = ImageGenerationService(
        api_key="key",
        model="gpt-image-1",
        size="1024x1024",
        quality="auto",
        workspace=tmp_path,
        client=_EmptyClient(),
    )

    with pytest.raises(RuntimeError, match="no image data"):
        await service.generate("nothing")
