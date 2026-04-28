"""Image generation service."""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from nanobot.config.paths import get_media_dir


@dataclass(frozen=True)
class ImageGenerationResult:
    path: str
    filename: str
    provider: str
    model: str


class ImageGenerationService:
    """Generate images through the configured provider and persist them locally."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        size: str,
        quality: str,
        workspace: str | Path,
        api_base: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.size = size
        self.quality = quality
        self.workspace = Path(workspace)
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
            max_retries=0,
        )

    async def generate(
        self,
        prompt: str,
        *,
        size: str | None = None,
        quality: str | None = None,
    ) -> ImageGenerationResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "size": size or self.size,
            "quality": quality or self.quality,
            "n": 1,
        }
        if self.model.startswith("dall-e-"):
            kwargs["response_format"] = "b64_json"

        response = await self._client.images.generate(**kwargs)
        data = getattr(response, "data", None) or []
        first = data[0] if data else None
        b64 = getattr(first, "b64_json", None) if first is not None else None
        if not b64:
            raise RuntimeError("image generation returned no image data")

        raw = base64.b64decode(b64)
        media_dir = get_media_dir("generated", workspace=self.workspace)
        filename = f"{uuid.uuid4().hex[:12]}.png"
        path = media_dir / filename
        path.write_bytes(raw)
        return ImageGenerationResult(
            path=str(path),
            filename=filename,
            provider="openai",
            model=self.model,
        )
