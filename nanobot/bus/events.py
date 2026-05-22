"""Event types for the message bus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Optional ``OutboundMessage.metadata`` key for structured, channel-agnostic UI
# payloads. Value is JSON-serializable with at least ``kind``; rich clients may
# render it and other channels may ignore unknown keys.
OUTBOUND_META_AGENT_UI = "_agent_ui"


@dataclass
class InboundMessage:
    """Message received from a chat channel."""

    channel: str  # telegram, discord, slack, whatsapp
    sender_id: str  # User identifier
    chat_id: str  # Chat/channel identifier
    content: str  # Message text
    timestamp: datetime = field(default_factory=datetime.now)
    media: list[str] = field(default_factory=list)  # Media URLs
    metadata: dict[str, Any] = field(default_factory=dict)  # Channel-specific data
    session_key_override: str | None = None  # Optional override for thread-scoped sessions

    @property
    def session_key(self) -> str:
        """Unique key for session identification."""
        if self.session_key_override:
            return self.session_key_override
        thread_id = self.metadata.get("message_thread_id")
        if thread_id is not None:
            return f"{self.channel}:{self.chat_id}:topic:{thread_id}"
        return f"{self.channel}:{self.chat_id}"


@dataclass
class OutboundMessage:
    """Message to send to a chat channel.

    ``metadata`` can carry routing (``message_id``, …), trace flags (``_progress``),
    and optional ``OUTBOUND_META_AGENT_UI`` blobs for rich clients; non-WebUI
    channels may ignore unknown keys.
    """

    channel: str
    chat_id: str
    content: str
    reply_to: str | None = None
    media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    buttons: list[list[str]] = field(default_factory=list)

    def __contains__(self, item: object) -> bool:
        """Support simple string containment checks against content in tests/callers."""
        return isinstance(item, str) and item in self.content
