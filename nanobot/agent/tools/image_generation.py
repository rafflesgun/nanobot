"""Tool for generating and sending images."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Awaitable, Callable

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.schema import StringSchema, tool_parameters_schema
from nanobot.bus.events import OutboundMessage
from nanobot.image_generation import ImageGenerationService

_SIZE_OPTIONS = (
    "auto",
    "1024x1024",
    "1024x1536",
    "1536x1024",
    "256x256",
    "512x512",
    "1792x1024",
    "1024x1792",
)
_QUALITY_OPTIONS = ("auto", "low", "medium", "high", "standard", "hd")


@tool_parameters(
    tool_parameters_schema(
        prompt=StringSchema("Image prompt to generate", min_length=1),
        size=StringSchema("Optional image size override", enum=_SIZE_OPTIONS, nullable=True),
        quality=StringSchema(
            "Optional image quality override",
            enum=_QUALITY_OPTIONS,
            nullable=True,
        ),
        required=["prompt"],
    )
)
class GenerateImageTool(Tool):
    """Generate an image and send it to the current chat."""

    def __init__(
        self,
        service: ImageGenerationService,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
    ) -> None:
        self._service = service
        self._send_callback = send_callback
        self._channel: ContextVar[str] = ContextVar("generate_image_channel", default="")
        self._chat_id: ContextVar[str] = ContextVar("generate_image_chat_id", default="")
        self._message_id: ContextVar[str | None] = ContextVar(
            "generate_image_message_id",
            default=None,
        )
        self._thread_id: ContextVar[int | None] = ContextVar(
            "generate_image_thread_id",
            default=None,
        )
        self._metadata: ContextVar[dict[str, Any]] = ContextVar(
            "generate_image_metadata",
            default={},
        )

    @property
    def name(self) -> str:
        return "generate_image"

    @property
    def description(self) -> str:
        return "Generate an image and send it to the current chat."

    def set_context(
        self,
        channel: str,
        chat_id: str,
        message_id: str | None = None,
        thread_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> None:
        """Set the current target chat context."""
        self._channel.set(channel)
        self._chat_id.set(chat_id)
        self._message_id.set(message_id)
        self._thread_id.set(thread_id)
        self._metadata.set(metadata or {})

    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Set the callback used to send generated images."""
        self._send_callback = callback

    async def execute(
        self,
        prompt: str,
        size: str | None = None,
        quality: str | None = None,
    ) -> str:
        channel = self._channel.get()
        chat_id = self._chat_id.get()
        if not channel or not chat_id:
            return "Error: No target channel/chat specified"
        if not self._send_callback:
            return "Error: Message sending not configured"

        try:
            result = await self._service.generate(prompt, size=size, quality=quality)
        except Exception:
            return "Error: Image generation failed."

        metadata = dict(self._metadata.get())
        message_id = self._message_id.get()
        thread_id = self._thread_id.get()
        if message_id is not None:
            metadata["message_id"] = message_id
        if thread_id is not None:
            metadata["message_thread_id"] = thread_id

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content="Generated image",
            media=[result.path],
            metadata=metadata,
        )
        try:
            await self._send_callback(msg)
        except Exception:
            return "Image generated but failed to send."
        return "Image generated and sent."
