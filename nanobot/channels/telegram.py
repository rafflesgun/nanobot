"""Telegram channel implementation using python-telegram-bot."""

from __future__ import annotations

import asyncio
import random
import re
import time
import unicodedata
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReactionTypeEmoji,
    ReplyParameters,
    Update,
)
HAS_REACTION_TYPE = True
from telegram.error import BadRequest, NetworkError, TimedOut
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

from io import BytesIO

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.paths import load_tts_overrides, save_tts_overrides
from nanobot.channels.base import BaseChannel
from nanobot.config.paths import get_media_dir
from nanobot.config.schema import Base, TTSConfig as SchemaTTSConfig
from nanobot.security.network import validate_url_target
from nanobot.tts.manager import TTSManager
from nanobot.utils.audio import convert_to_ogg_opus, get_audio_duration
from nanobot.utils.helpers import split_message

TELEGRAM_MAX_MESSAGE_LEN = 4000  # Telegram message character limit
# Telegram's actual API limit is 4096; we split raw markdown at 4000 as a
# safety margin for mid-stream edits (plain text).  For _stream_end, we
# convert to HTML first and then split at the true 4096-char boundary so
# the final rendered message never overflows.
TELEGRAM_HTML_MAX_LEN = 4096
TELEGRAM_REPLY_CONTEXT_MAX_LEN = (
    TELEGRAM_MAX_MESSAGE_LEN  # Max length for reply context in user message
)
FORWARD_DEBOUNCE_MS = 80


# ACK reaction emojis pool
TELEGRAM_ACK_REACTIONS = ["⚡️", "👌", "👀", "🔥", "👍"]


def _random_ack_reaction() -> str:
    """Return a random emoji from the ACK reactions pool."""
    return random.choice(TELEGRAM_ACK_REACTIONS)


def _strip_md(s: str) -> str:
    """Strip markdown inline formatting from text."""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    s = re.sub(r"~~(.+?)~~", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    return s.strip()


def _strip_md_block(text: str) -> str:
    """Strip block-level and inline markdown for readable plain-text preview.

    Used during streaming mid-edits so users see clean text instead of raw
    markdown syntax while the response is still being generated.
    """
    # Code blocks -> just the code
    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", r"\1", text)
    # Headers -> plain text
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)
    # Blockquotes
    text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)
    # Bold / italic / strikethrough
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    # Inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Bullet lists
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)
    # Numbered lists (normalize spacing)
    text = re.sub(r"^(\d+)\.\s+", r"\1. ", text, flags=re.MULTILINE)
    return text


def _render_table_box(table_lines: list[str]) -> str:
    """Convert markdown pipe-table to compact aligned text for <pre> display."""

    def dw(s: str) -> int:
        return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)

    rows: list[list[str]] = []
    has_sep = False
    for line in table_lines:
        cells = [_strip_md(c) for c in line.strip().strip("|").split("|")]
        if all(re.match(r"^:?-+:?$", c) for c in cells if c):
            has_sep = True
            continue
        rows.append(cells)
    if not rows or not has_sep:
        return "\n".join(table_lines)

    ncols = max(len(r) for r in rows)
    for r in rows:
        r.extend([""] * (ncols - len(r)))
    widths = [max(dw(r[c]) for r in rows) for c in range(ncols)]

    def dr(cells: list[str]) -> str:
        return "  ".join(f"{c}{' ' * (w - dw(c))}" for c, w in zip(cells, widths))

    out = [dr(rows[0])]
    out.append("  ".join("─" * w for w in widths))
    for row in rows[1:]:
        out.append(dr(row))
    return "\n".join(out)


def _markdown_to_telegram_html(text: str) -> str:
    """
    Convert markdown to Telegram-safe HTML.
    """
    if not text:
        return ""

    # 1. Extract and protect code blocks (preserve content from other processing)
    code_blocks: list[str] = []

    def save_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", save_code_block, text)

    # 1.5. Convert markdown tables to box-drawing (reuse code_block placeholders)
    lines = text.split("\n")
    rebuilt: list[str] = []
    li = 0
    while li < len(lines):
        if re.match(r"^\s*\|.+\|", lines[li]):
            tbl: list[str] = []
            while li < len(lines) and re.match(r"^\s*\|.+\|", lines[li]):
                tbl.append(lines[li])
                li += 1
            box = _render_table_box(tbl)
            if box != "\n".join(tbl):
                code_blocks.append(box)
                rebuilt.append(f"\x00CB{len(code_blocks) - 1}\x00")
            else:
                rebuilt.extend(tbl)
        else:
            rebuilt.append(lines[li])
            li += 1
    text = "\n".join(rebuilt)

    # 2. Extract and protect inline code
    inline_codes: list[str] = []

    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", save_inline_code, text)

    # 3. Headers # Title -> <b>Title</b> (preserve visual hierarchy)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"⟪B⟫\1⟪/B⟫", text, flags=re.MULTILINE)

    # 4. Blockquotes > text -> just the text (before HTML escaping)
    text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)

    # 5. Escape HTML special characters
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 6. Links [text](url) - must be before bold/italic to handle nested cases
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # 7. Bold **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # 7b. Bold *text* (single asterisk) — after ** is consumed
    # Matches *word* and *multi word* but not "* bullet" (asterisk + space at start)
    text = re.sub(r"\*(\S(?:[^*]*\S)?)\*(?!\*)", r"<b>\1</b>", text)

    # 8. Italic _text_ (avoid matching inside words like some_var_name)
    text = re.sub(r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])", r"<i>\1</i>", text)

    # 9. Strikethrough ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # 10. Bullet lists - item -> • item
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)

    # 10.5. Numbered lists  1. item -> 1. item (keep number, normalize indent)
    text = re.sub(r"^(\d+)\.\s+", r"\1. ", text, flags=re.MULTILINE)

    # 11. Restore inline code with HTML tags
    for i, code in enumerate(inline_codes):
        # Escape HTML in code content
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")

    # 12. Restore code blocks with HTML tags
    for i, code in enumerate(code_blocks):
        # Escape HTML in code content
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")

    # 13. Restore header bold markers (inserted in step 3, after HTML escaping)
    text = text.replace("⟪B⟫", "<b>").replace("⟪/B⟫", "</b>")

    return text


_SEND_MAX_RETRIES = 3
_SEND_RETRY_BASE_DELAY = 0.5  # seconds, doubled each retry
_STREAM_EDIT_INTERVAL_DEFAULT = 0.6  # min seconds between edit_message_text calls


@dataclass
class _StreamBuf:
    """Per-chat streaming accumulator for progressive message editing."""

    text: str = ""
    message_id: int | None = None
    last_edit: float = 0.0
    thread_id: int | None = None
    stream_id: str | None = None


@dataclass
class _QueuedTelegramUpdate:
    """Telegram update staged for per-session ordered processing."""

    kind: Literal["command", "message"]
    update: Update
    context: Any
    sort_key: tuple[int, int]


class TelegramConfig(Base):
    """Telegram channel configuration."""

    enabled: bool = False
    token: str = ""
    mode: Literal["polling", "webhook"] = "polling"
    allow_from: list[str] = Field(default_factory=list)
    proxy: str | None = None
    reply_to_message: bool = False
    react_emoji: str | list[str] = Field(default_factory=lambda: ["⚡️", "👌", "👀", "🔥", "👍"])
    group_policy: Literal["open", "mention"] = "mention"
    connection_pool_size: int = 32
    pool_timeout: float = 5.0
    streaming: bool = True
    tts: SchemaTTSConfig = Field(default_factory=SchemaTTSConfig)
    # Enable inline keyboard buttons in Telegram messages.
    inline_keyboards: bool = False
    stream_edit_interval: float = Field(default=_STREAM_EDIT_INTERVAL_DEFAULT, ge=0.1)
    webhook_url: str = ""
    webhook_listen_host: str = "127.0.0.1"
    webhook_listen_port: int = Field(default=8081, ge=1, le=65535)
    webhook_path: str = "/telegram"
    webhook_secret_token: str = ""
    webhook_max_connections: int = Field(default=4, ge=1, le=100)

    @field_validator("webhook_path")
    @classmethod
    def webhook_path_must_start_with_slash(cls, value: str) -> str:
        value = value.strip() or "/telegram"
        if not value.startswith("/"):
            raise ValueError('webhook_path must start with "/"')
        return value

    @model_validator(mode="after")
    def validate_webhook_config(self) -> "TelegramConfig":
        if self.mode != "webhook":
            return self

        url = self.webhook_url.strip()
        if not url:
            raise ValueError("webhook_url is required when Telegram mode is webhook")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("webhook_url must be a public HTTPS URL")
        secret = self.webhook_secret_token.strip()
        if not secret:
            raise ValueError("webhook_secret_token is required when Telegram mode is webhook")
        if len(secret) > 256 or re.match(r"^[A-Za-z0-9_-]+$", secret) is None:
            raise ValueError(
                "webhook_secret_token must be 1-256 characters using only A-Z, a-z, 0-9, _ and -"
            )
        return self


class TelegramChannel(BaseChannel):
    """
    Telegram channel using long polling or webhook mode.

    Long polling is the default. Webhook mode requires a public HTTPS URL and a
    Telegram secret token.
    """

    name = "telegram"
    display_name = "Telegram"

    # Commands registered with Telegram's command menu
    BOT_COMMANDS = [
        BotCommand("start", "Start the bot"),
        BotCommand("new", "Start a new conversation"),
        BotCommand("stop", "Stop the current task"),
        BotCommand("model", "Show or switch the LLM model"),
        BotCommand("tts", "Control TTS settings (on/off, voices, voice, provider)"),
        BotCommand("trace", "Toggle agent trace output (on/off/status)"),
        BotCommand("stats", "Show token usage statistics"),
        BotCommand("restart", "Restart the bot"),
        BotCommand("status", "Show bot status"),
        BotCommand("history", "Show recent conversation messages"),
        BotCommand("goal", "Start a sustained objective (long-running task)"),
        BotCommand("pairing", "Manage DM pairing (approve/deny/list)"),
        BotCommand("model", "Switch runtime model preset"),
        BotCommand("dream", "Run Dream memory consolidation now"),
        BotCommand("dream_log", "Show the latest Dream memory change"),
        BotCommand("dream_restore", "Restore Dream memory to an earlier version"),
        BotCommand("help", "Show available commands"),
    ]

    # Regex for slash commands routed to AgentLoop via ``_forward_command``.
    # Hyphenated ``dream-*`` commands stay on a separate handler (below).
    TELEGRAM_BUS_SLASH_COMMAND_RE = re.compile(
        r"^/(?:new|stop|restart|status|dream|history|goal|pairing|model)(?:@\w+)?(?:\s+.*)?$"
    )

    @classmethod
    def default_config(cls) -> dict[str, Any]:
        return TelegramConfig().model_dump(by_alias=True)

    _STREAM_EDIT_INTERVAL = 0.6  # min seconds between edit_message_text calls

    def __init__(
        self,
        config: Any,
        bus: MessageBus,
        groq_api_key: str = "",
        workspace_path: str | None = None,
    ):
        if isinstance(config, dict):
            config = TelegramConfig.model_validate(config)
        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self.groq_api_key = groq_api_key
        self._workspace_path = workspace_path
        self._app: Application | None = None
        self._typing_tasks: dict[str, asyncio.Task] = {}  # composite_key -> typing loop task
        self._thinking_messages: dict[str, int] = {}  # composite_key -> thinking message_id
        self._media_group_buffers: dict[str, dict] = {}
        self._media_group_tasks: dict[str, asyncio.Task] = {}
        self._debounce_buffers: dict[str, dict[str, Any]] = {}
        self._message_threads: dict[tuple[str, int], int] = {}
        self._bot_user_id: int | None = None
        self._bot_username: str | None = None

        # TTS manager initialization
        self.tts_manager = TTSManager(config.tts)

        # Per-chat TTS overrides (for /tts command)
        self._chat_tts_overrides: dict[str, dict] = load_tts_overrides()

        # Per-chat trace toggle (runtime-only, resets on restart).
        # When True, intermediate thinking/tool-hint progress messages are
        # forwarded to the chat prefixed with "🤖 ".  Default is False (suppress).
        self._trace_enabled: dict[str, bool] = {}
        self._stream_bufs: dict[str, _StreamBuf] = {}  # chat_id -> streaming state
        self._inbound_buffers: dict[str, list[_QueuedTelegramUpdate]] = {}
        self._inbound_workers: dict[str, asyncio.Task] = {}

    def is_allowed(self, sender_id: str) -> bool:
        """Preserve Telegram's legacy id|username allowlist matching."""
        # Do NOT call super().is_allowed() — it is too permissive for legacy format
        # if super().is_allowed(sender_id):
        #     return True

        allow_list = getattr(self.config, "allow_from", [])
        if not allow_list:
            return False
        if "*" in allow_list:
            return True

        sender_str = str(sender_id)

        # Check if the entire sender string matches any entry in allow_from
        if sender_str in allow_list:
            return True

        # Check legacy format: id|username
        parts = sender_str.split("|")
        if len(parts) != 2:  # Legacy format is strictly id|username
            return False

        sid, username = parts
        if not sid.isdigit() or not username:
            return False

        return sid in allow_list or username in allow_list

    @staticmethod
    def _normalize_telegram_command(content: str) -> str:
        """Map Telegram-safe command aliases back to canonical nanobot commands."""
        if not content.startswith("/"):
            return content
        if content == "/dream_log" or content.startswith("/dream_log "):
            return content.replace("/dream_log", "/dream-log", 1)
        if content == "/dream_restore" or content.startswith("/dream_restore "):
            return content.replace("/dream_restore", "/dream-restore", 1)
        return content

    async def start(self) -> None:
        """Start the Telegram bot."""
        if not self.config.token:
            self.logger.error("bot token not configured")
            return

        self._running = True

        proxy = self.config.proxy or None

        # Separate pools so long-polling (getUpdates) never starves outbound sends.
        api_request = HTTPXRequest(
            connection_pool_size=self.config.connection_pool_size,
            pool_timeout=self.config.pool_timeout,
            connect_timeout=30.0,
            read_timeout=30.0,
            proxy=proxy,
        )
        poll_request = HTTPXRequest(
            connection_pool_size=4,
            pool_timeout=self.config.pool_timeout,
            connect_timeout=30.0,
            read_timeout=30.0,
            proxy=proxy,
        )
        builder = (
            Application.builder()
            .token(self.config.token)
            .request(api_request)
            .get_updates_request(poll_request)
        )
        self._app = builder.build()
        self._app.add_error_handler(self._on_error)

        # Command handlers — private chats only.
        # In group chats, commands must be sent as "@BotName /command" (plain text
        # mention), which flows through _on_message where the mention check and
        # @-prefix stripping are applied.  This avoids ambiguity with the
        # /command@BotName Telegram syntax and prevents other bots from picking up
        # commands not meant for them.
        private_only = filters.ChatType.PRIVATE
        self._app.add_handler(CommandHandler("start", self._on_start, filters=private_only))
        self._app.add_handler(CommandHandler("new", self._forward_command, filters=private_only))
        self._app.add_handler(CommandHandler("stop", self._forward_command, filters=private_only))
        self._app.add_handler(CommandHandler("model", self._forward_command, filters=private_only))
        self._app.add_handler(CommandHandler("help", self._on_help, filters=private_only))
        self._app.add_handler(CommandHandler("tts", self._on_tts_command, filters=private_only))
        self._app.add_handler(CommandHandler("trace", self._on_trace_command, filters=private_only))
        self._app.add_handler(CommandHandler("stats", self._on_stats_command, filters=private_only))
        self._app.add_handler(
<<<<<<< HEAD
            CommandHandler("restart", self._forward_command, filters=private_only)
=======
            MessageHandler(
                filters.Regex(TelegramChannel.TELEGRAM_BUS_SLASH_COMMAND_RE),
                self._forward_command,
            )
>>>>>>> origin/main
        )
        self._app.add_handler(CommandHandler("status", self._forward_command, filters=private_only))

        # Add message handler for text, photos, voice, documents.
        # In groups, commands typed as "@BotName /cmd" are plain TEXT (not COMMAND
        # entities from Telegram's perspective when prefixed by a mention), so we
        # include all TEXT here.  The ~filters.COMMAND exclusion only applies
        # private chats where CommandHandlers above take precedence.
        self._app.add_handler(
            MessageHandler(
                (
                    filters.TEXT
                    | filters.PHOTO
                    | filters.VIDEO
                    | filters.VIDEO_NOTE
                    | filters.ANIMATION
                    | filters.VOICE
                    | filters.AUDIO
                    | filters.Document.ALL
                    | filters.LOCATION
                ),
                self._on_message,
            )
        )

        # Conditionally register inline keyboard callback handler
        if self.config.inline_keyboards:
            self._app.add_handler(CallbackQueryHandler(self._on_callback_query))
            allowed_updates = ["message", "callback_query"]
            self.logger.debug("inline keyboards enabled")
        else:
            allowed_updates = ["message"]

        if self.config.mode == "webhook":
            self.logger.info("Starting bot (webhook mode)...")
        else:
            self.logger.info("Starting bot (polling mode)...")

        # Initialize and start receiving updates
        await self._app.initialize()
        await self._app.start()

        # Get bot info and register command menu
        bot_info = await self._app.bot.get_me()
        self._bot_user_id = getattr(bot_info, "id", None)
        self._bot_username = getattr(bot_info, "username", None)
        self.logger.info("bot @{} connected", bot_info.username)

        try:
            await self._app.bot.set_my_commands(self.BOT_COMMANDS)
            self.logger.debug("bot commands registered")
        except Exception as e:
            self.logger.warning("Failed to register bot commands: {}", e)

<<<<<<< HEAD
        # Start polling (this runs until stopped)
        await self._app.updater.start_polling(
            allowed_updates=allowed_updates,
            drop_pending_updates=True,  # Ignore old messages on startup
            error_callback=self._on_polling_error,
        )
=======
        if self.config.mode == "webhook":
            # ``url_path`` is the local HTTP route. ``webhook_url`` is the
            # public HTTPS URL Telegram calls; reverse proxies may rewrite it.
            await self._app.updater.start_webhook(
                listen=self.config.webhook_listen_host,
                port=self.config.webhook_listen_port,
                url_path=self.config.webhook_path.lstrip("/"),
                webhook_url=self.config.webhook_url.strip(),
                allowed_updates=allowed_updates,
                drop_pending_updates=False,
                secret_token=self.config.webhook_secret_token.strip(),
                max_connections=self.config.webhook_max_connections,
            )
        else:
            # Start polling (this runs until stopped)
            await self._app.updater.start_polling(
                allowed_updates=allowed_updates,
                drop_pending_updates=False,  # Process pending messages on startup
                error_callback=self._on_polling_error,
            )
>>>>>>> origin/main

        # Keep running until stopped
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        self._running = False

        # Cancel all typing indicators
        for chat_id in list(self._typing_tasks):
            self._stop_typing(chat_id)

        for task in self._media_group_tasks.values():
            task.cancel()
        self._media_group_tasks.clear()
        self._media_group_buffers.clear()

<<<<<<< HEAD
        for buf in self._debounce_buffers.values():
            task = buf.get("task")
            if task and not task.done():
                task.cancel()
        self._debounce_buffers.clear()
=======
        for task in self._inbound_workers.values():
            task.cancel()
        self._inbound_workers.clear()
        self._inbound_buffers.clear()
>>>>>>> origin/main

        if self._app:
            self.logger.info("Stopping bot...")
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None

    @staticmethod
    def _get_media_type(path: str) -> str:
        """Guess media type from file extension."""
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext in ("jpg", "jpeg", "png", "gif", "webp"):
            return "photo"
        if ext in ("mp4", "mov", "avi", "mkv", "webm", "3gp"):
            return "video"
        if ext == "ogg":
            return "voice"
        if ext in ("mp3", "m4a", "wav", "aac"):
            return "audio"
        return "document"

    @staticmethod
    def _composite_key(chat_id: str, thread_id: int | None = None) -> str:
        """Build a composite key for typing/thinking state dicts."""
        return f"{chat_id}:{thread_id}" if thread_id else chat_id

    @staticmethod
    def _tts_scope_key(chat_id: str, thread_id: int | None = None) -> str:
        """Scope TTS overrides to the current chat or topic thread."""
        return f"{chat_id}:{thread_id}" if thread_id else chat_id

    @staticmethod
    def _is_remote_media_url(path: str) -> bool:
        return path.startswith(("http://", "https://"))

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Telegram."""
        if not self._app:
            self.logger.warning("bot not running")
            return

<<<<<<< HEAD
        thread_id = msg.metadata.get("message_thread_id")
        comp_key = self._composite_key(msg.chat_id, thread_id)

        is_progress = msg.metadata.get("_progress", False)

        # Only stop typing indicator for final responses
        if not is_progress:
            self._stop_typing(comp_key)
=======
        # Only stop typing indicator and remove reaction for final responses
        if not msg.metadata.get("_progress", False):
            self._stop_typing(msg.chat_id)
            if reply_to_message_id := msg.metadata.get("message_id"):
                with suppress(ValueError):
                    await self._remove_reaction(msg.chat_id, int(reply_to_message_id))
>>>>>>> origin/main

        try:
            chat_id = int(msg.chat_id)
        except ValueError:
            self.logger.exception("Invalid chat_id: {}", msg.chat_id)
            return

        # ── Progress messages (thinking / tool hints) ──────────────────
        # These are intermediate AI thoughts and tool-call hints produced
        # while the agent is still working.  They should NOT be sent to
        # the Telegram channel — the user only sees the "Typing…" indicator
        # and the "💭 Thinking…" draft message (DM only).
        # When trace is enabled per chat, they are sent prefixed with 🤖 or 💭.
        if is_progress:
            is_tool_hint = msg.metadata.get("_tool_hint", False)
            label = "tool_hint" if is_tool_hint else "thinking"
            preview = (msg.content or "")[:120].replace("\n", " ")
            logger.info("[progress:{}] chat={} → {}", label, msg.chat_id, preview)

            trace_on = self._trace_enabled.get(str(chat_id), False)
            if not trace_on and thread_id is None:
                return  # suppressed - only logged

            # Trace enabled → send to chat with prefix
            prefix = ""
            if trace_on:
                prefix = "🤖 " if is_tool_hint else "💭 "
            trace_content = prefix + (msg.content or "").strip()

            # Prepare sending parameters (reuse existing thread/reply logic)
            thread_kwargs: dict = {}
            if thread_id is not None:
                thread_kwargs["message_thread_id"] = thread_id

            reply_params = None
            if self.config.reply_to_message:
                reply_to_message_id = msg.metadata.get("message_id")
                if reply_to_message_id:
                    reply_params = ReplyParameters(
                        message_id=reply_to_message_id, allow_sending_without_reply=True
                    )

            # Send (split if too long)
            for chunk in split_message(trace_content, TELEGRAM_MAX_MESSAGE_LEN):
                try:
                    html = _markdown_to_telegram_html(chunk)
                    await self._app.bot.send_message(
                        chat_id=chat_id,
                        text=html,
                        parse_mode="HTML",
                        reply_parameters=reply_params,
                        **thread_kwargs,
                    )
                except Exception as e:
                    logger.warning("Failed to send trace message: {}", e)
                    try:
                        await self._app.bot.send_message(
                            chat_id=chat_id,
                            text=chunk,
                            reply_parameters=reply_params,
                            **thread_kwargs,
                        )
                    except Exception as e2:
                        logger.error("Error sending trace message: {}", e2)

            return  # progress message handled

        # Build optional kwargs for message_thread_id (topic support)
        thread_kwargs: dict = {}
        if thread_id is not None:
            thread_kwargs["message_thread_id"] = thread_id

        # Infer topic from cached reply-to message_id if not already set
        if "message_id" in msg.metadata and "message_thread_id" not in thread_kwargs:
            cached_thread_id = self._message_threads.get((msg.chat_id, msg.metadata["message_id"]))
            if cached_thread_id is not None:
                thread_kwargs["message_thread_id"] = cached_thread_id

        # Check if there's a thinking message to delete
        thinking_msg_id = self._thinking_messages.pop(comp_key, None)
        if thinking_msg_id:
            try:
                await self._app.bot.delete_message(chat_id=chat_id, message_id=thinking_msg_id)
                logger.debug("Deleted thinking message {}", thinking_msg_id)
            except Exception as e:
                logger.debug("Failed to delete thinking message: {}", e)

        reply_params = None
        if self.config.reply_to_message:
            reply_to_message_id = msg.metadata.get("message_id")
            if reply_to_message_id:
                reply_params = ReplyParameters(
                    message_id=reply_to_message_id, allow_sending_without_reply=True
                )

        # Send media files
        for media_path in msg.media or []:
            try:
                media_type = self._get_media_type(media_path)
                sender = {
                    "photo": self._app.bot.send_photo,
                    "video": self._app.bot.send_video,
                    "voice": self._app.bot.send_voice,
                    "audio": self._app.bot.send_audio,
                }.get(media_type, self._app.bot.send_document)
                param = {
                    "photo": "photo",
                    "video": "video",
                    "voice": "voice",
                    "audio": "audio",
                }.get(media_type, "document")
                extra: dict[str, Any] = {}
                if media_type == "video":
                    extra["supports_streaming"] = True

                # Telegram Bot API accepts HTTP(S) URLs directly for media params.
                if self._is_remote_media_url(media_path):
                    ok, error = validate_url_target(media_path)
                    if not ok:
                        raise ValueError(f"unsafe media URL: {error}")
                    await self._call_with_retry(
                        sender,
                        chat_id=chat_id,
                        **{param: media_path},
                        reply_parameters=reply_params,
                        **thread_kwargs,
                        **extra,
                    )
                    continue

                media_bytes = Path(media_path).read_bytes()
                filename = Path(media_path).name
                send_kwargs = {param: media_bytes, "filename": filename}
                await self._call_with_retry(
                    sender,
                    chat_id=chat_id,
                    reply_parameters=reply_params,
                    **thread_kwargs,
                    **extra,
                    **send_kwargs,
                )
            except Exception:
                filename = media_path.rsplit("/", 1)[-1]
                self.logger.exception("Failed to send media {}", media_path)
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=f"[Failed to send: {filename}]",
                    reply_parameters=reply_params,
                    **thread_kwargs,
                )

        # Send text content
        if msg.content and msg.content != "[empty message]":
            render_as_blockquote = bool(msg.metadata.get("_tool_hint"))
            buttons = getattr(msg, "buttons", None) or []
            reply_markup = self._build_keyboard(buttons) if buttons else None
            text = msg.content
            # Fallback: no native keyboard → splice labels into the message so the choices survive.
            if buttons and reply_markup is None:
                text = f"{text}\n\n{self._buttons_as_text(buttons)}"
            chunks = split_message(text, TELEGRAM_MAX_MESSAGE_LEN)
            for i, chunk in enumerate(chunks):
                is_last = (i == len(chunks) - 1)
                await self._send_text(
                    chat_id, chunk, reply_params, thread_kwargs,
                    render_as_blockquote=render_as_blockquote,
                    reply_markup=reply_markup if is_last else None,
                )

        await self._maybe_send_tts(
            chat_id=chat_id,
            text=msg.content,
            reply_params=reply_params,
            thread_kwargs=thread_kwargs,
            metadata=msg.metadata,
        )

    async def _call_with_retry(self, fn, *args, **kwargs):
        """Call an async Telegram API function with retry on pool/network timeout and RetryAfter."""
        from telegram.error import RetryAfter

        for attempt in range(1, _SEND_MAX_RETRIES + 1):
            try:
                return await fn(*args, **kwargs)
            except TimedOut:
                if attempt == _SEND_MAX_RETRIES:
                    raise
                delay = _SEND_RETRY_BASE_DELAY * (2 ** (attempt - 1))
<<<<<<< HEAD
                logger.warning(
                    "Telegram timeout (attempt {}/{}), retrying in {:.1f}s",
                    attempt,
                    _SEND_MAX_RETRIES,
                    delay,
=======
                self.logger.warning(
                    "timeout (attempt {}/{}), retrying in {:.1f}s",
                    attempt, _SEND_MAX_RETRIES, delay,
>>>>>>> origin/main
                )
                await asyncio.sleep(delay)
            except RetryAfter as e:
                if attempt == _SEND_MAX_RETRIES:
                    raise
<<<<<<< HEAD
                delay = float(getattr(e, "retry_after", _SEND_RETRY_BASE_DELAY))
                logger.warning(
                    "Telegram rate limited (attempt {}/{}), retrying in {:.1f}s",
                    attempt,
                    _SEND_MAX_RETRIES,
                    delay,
=======
                delay = float(e.retry_after)
                self.logger.warning(
                    "Flood Control (attempt {}/{}), retrying in {:.1f}s",
                    attempt, _SEND_MAX_RETRIES, delay,
>>>>>>> origin/main
                )
                await asyncio.sleep(delay)

    @staticmethod
    def _is_not_modified_error(exc: Exception) -> bool:
        return isinstance(exc, BadRequest) and "message is not modified" in str(exc).lower()

    async def _send_text(
        self,
        chat_id: int,
        text: str,
        reply_params=None,
        thread_kwargs: dict | None = None,
        render_as_blockquote: bool = False,
        reply_markup=None,
    ) -> None:
        """Send a plain text message with HTML fallback."""
        try:
            html = _markdown_to_telegram_html(text)
            await self._call_with_retry(
                self._app.bot.send_message,
                chat_id=chat_id,
                text=html,
                parse_mode="HTML",
                reply_parameters=reply_params,
                reply_markup=reply_markup,
                **(thread_kwargs or {}),
            )
        except BadRequest as e:
            self.logger.warning("HTML parse failed, falling back to plain text: {}", e)
            try:
                await self._call_with_retry(
                    self._app.bot.send_message,
                    chat_id=chat_id,
                    text=text,
                    reply_parameters=reply_params,
                    reply_markup=reply_markup,
                    **(thread_kwargs or {}),
                )
            except Exception:
                self.logger.exception("Error sending message")
                raise

    def _get_tts_override(self, chat_id: str, thread_id: int | None = None) -> dict[str, Any]:
        """Resolve TTS overrides with topic-specific settings taking precedence."""
        base = dict(self._chat_tts_overrides.get(chat_id, {}))
        if thread_id is None:
            return base
        scoped = self._chat_tts_overrides.get(self._tts_scope_key(chat_id, thread_id), {})
        return {**base, **scoped}

    async def _maybe_send_tts(
        self,
        *,
        chat_id: int,
        text: str | None,
        reply_params,
        thread_kwargs: dict[str, Any] | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Best-effort TTS delivery for final assistant responses."""
        if not self._app or not text or not text.strip():
            return

        meta = metadata or {}
        thread_kwargs = thread_kwargs or {}
        thread_id = thread_kwargs.get("message_thread_id", meta.get("message_thread_id"))
        chat_id_str = str(chat_id)
        chat_override = self._get_tts_override(chat_id_str, thread_id)
        tts_enabled = chat_override.get("enabled", self.tts_manager.config.enabled)
        if not tts_enabled:
            return

        is_command_response = False
        if meta.get("command_response", False):
            is_command_response = True
            logger.debug("Skipping TTS for command response")
        elif meta.get("render_as") == "text":
            is_command_response = True
            logger.debug("Skipping TTS for text-rendered command response")
        else:
            content_stripped = text.strip()
            if (
                content_stripped.startswith("/model")
                or content_stripped.startswith("/tts")
                or content_stripped.startswith("/trace")
                or content_stripped.startswith("/stats")
            ):
                is_command_response = True
                logger.debug("Skipping TTS for command response (detected from content)")
        if is_command_response:
            return

        content = text.strip()
        if "|" in content and "---" in content:
            logger.debug("Skipping TTS for table-like message")
            return
        if content.startswith("{") and content.endswith("}"):
            logger.debug("Skipping TTS for JSON-like message")
            return
        if content.startswith("[") and content.endswith("]"):
            logger.debug("Skipping TTS for JSON array message")
            return
        if "Error:" in content and ":" in content:
            logger.debug("Skipping TTS for error message")
            return

        try:
            tts_config = self.config.tts.model_copy()
            if "voice" in chat_override:
                tts_config.voice = chat_override["voice"]
            if "provider" in chat_override:
                tts_config.provider = chat_override["provider"]
            if "enabled" in chat_override:
                tts_config.enabled = chat_override["enabled"]

            logger.debug(
                "TTS effective config: chat_id={} thread_id={} enabled={} provider={} voice={}",
                chat_id,
                thread_id,
                tts_config.enabled,
                tts_config.provider,
                tts_config.voice,
            )

            temp_tts_manager = TTSManager(tts_config)
            ogg_bytes = await temp_tts_manager.generate_voice_note(text)
            if not ogg_bytes:
                logger.warning("TTS returned no audio → skipping voice note")
                return

            duration = await get_audio_duration(ogg_bytes, "ogg")
            voice_file = BytesIO(ogg_bytes)
            voice_file.name = "voice_note.ogg"

            await self._app.bot.send_voice(
                chat_id=chat_id,
                voice=voice_file,
                duration=int(duration),
                reply_parameters=reply_params,
                **thread_kwargs,
            )
            logger.info("TTS voice note sent ({:.1f}s)", duration)
        except Exception:
            logger.exception("TTS generation or sending failed → falling back to text only")

    async def send_delta(
        self, chat_id: str, delta: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Progressive message editing: send on first delta, edit on subsequent ones."""
        if not self._app:
            return
        meta = metadata or {}
        int_chat_id = int(chat_id)
        thread_id = meta.get("message_thread_id")
        comp_key = self._composite_key(chat_id, thread_id)
        stream_id = meta.get("_stream_id")
        thread_kwargs = {"message_thread_id": thread_id} if thread_id is not None else {}

        if meta.get("_stream_end"):
            buf = self._stream_bufs.get(comp_key)
            if not buf or not buf.message_id or not buf.text:
                return
            if stream_id and buf.stream_id and buf.stream_id != stream_id:
                return
            self._stop_typing(comp_key)
            thinking_msg_id = self._thinking_messages.pop(comp_key, None)
            if thinking_msg_id:
                try:
                    await self._app.bot.delete_message(
                        chat_id=int_chat_id, message_id=thinking_msg_id
                    )
                except Exception as e:
                    logger.debug("Failed to delete thinking message after stream: {}", e)
            if reply_to_message_id := meta.get("message_id"):
                with suppress(ValueError):
                    await self._remove_reaction(chat_id, int(reply_to_message_id))
<<<<<<< HEAD
                except ValueError:
                    pass
            thread_kwargs = {"message_thread_id": thread_id} if thread_id is not None else {}
=======
            thread_kwargs = {}
            if message_thread_id := meta.get("message_thread_id"):
                thread_kwargs["message_thread_id"] = message_thread_id
>>>>>>> origin/main
            raw_text = buf.text
            html = _markdown_to_telegram_html(raw_text)
            if len(html) <= TELEGRAM_HTML_MAX_LEN:
                primary_html = html
                extra_html_chunks = []
            else:
                html_chunks = split_message(html, TELEGRAM_HTML_MAX_LEN)
                primary_html = html_chunks[0]
                extra_html_chunks = html_chunks[1:]
            try:
                await self._call_with_retry(
                    self._app.bot.edit_message_text,
                    chat_id=int_chat_id,
                    message_id=buf.message_id,
                    text=primary_html,
                    parse_mode="HTML",
                )
            except BadRequest as e:
                if self._is_not_modified_error(e):
<<<<<<< HEAD
                    logger.debug("Final stream edit already applied for {}", chat_id)
                    self._stream_bufs.pop(comp_key, None)
                    return
                logger.debug("Final stream edit failed (HTML), trying plain: {}", e)
                primary_plain = (
                    split_message(raw_text, TELEGRAM_MAX_MESSAGE_LEN)[0]
                    if len(raw_text) > TELEGRAM_MAX_MESSAGE_LEN
                    else raw_text
                )
=======
                    self.logger.debug("Final stream edit already applied for {}", chat_id)
                    self._stream_bufs.pop(chat_id, None)
                    return
                self.logger.debug("Final stream edit failed (HTML), trying plain: {}", e)
                # Fall back to raw markdown (not HTML) so users don't see raw tags.
                primary_plain = split_message(raw_text, TELEGRAM_MAX_MESSAGE_LEN)[0] if len(raw_text) > TELEGRAM_MAX_MESSAGE_LEN else raw_text
>>>>>>> origin/main
                try:
                    await self._call_with_retry(
                        self._app.bot.edit_message_text,
                        chat_id=int_chat_id,
                        message_id=buf.message_id,
                        text=primary_plain,
                    )
                except Exception as e2:
                    if self._is_not_modified_error(e2):
                        self.logger.debug("Final stream plain edit already applied for {}", chat_id)
                    else:
<<<<<<< HEAD
                        logger.warning("Final stream edit failed: {}", e2)
                        raise
=======
                        self.logger.warning("Final stream edit failed: {}", e2)
                        raise  # Let ChannelManager handle retry
>>>>>>> origin/main
            for extra_html_chunk in extra_html_chunks:
                try:
                    await self._call_with_retry(
                        self._app.bot.send_message,
                        chat_id=int_chat_id,
                        text=extra_html_chunk,
                        parse_mode="HTML",
                        **thread_kwargs,
                    )
                except Exception:
                    await self._send_text(int_chat_id, extra_html_chunk)
            self._stream_bufs.pop(comp_key, None)
            await self._maybe_send_tts(
                chat_id=int_chat_id,
                text=buf.text,
                reply_params=None,
                thread_kwargs=thread_kwargs,
                metadata=meta,
            )
            return

        buf = self._stream_bufs.get(comp_key)
        if buf is None or (stream_id and buf.stream_id and buf.stream_id != stream_id):
            buf = _StreamBuf(thread_id=thread_id, stream_id=stream_id)
            self._stream_bufs[comp_key] = buf
            buf.text = ""
            buf.message_id = None
        elif stream_id and not buf.stream_id:
            buf.stream_id = stream_id
        buf.text += delta

        if not buf.text.strip():
            return
        if meta.get("_stream_delta") and delta == "" and buf.message_id is not None:
            now = time.monotonic()
            if (now - buf.last_edit) >= 0:
                try:
                    await self._app.bot.edit_message_text(
                        chat_id=int_chat_id, message_id=buf.message_id, text=buf.text
                    )
                    buf.last_edit = now
                except Exception as e:
                    if e.__class__.__name__ == "BadRequest" and "not modified" in str(e).lower():
                        buf.last_edit = now
                    else:
                        logger.debug("Stream edit failed: {}", e)
                return

        now = time.monotonic()
        if buf.message_id is None:
            preview = _strip_md_block(buf.text)
            try:
                sent = await self._call_with_retry(
                    self._app.bot.send_message,
                    chat_id=int_chat_id,
                    text=preview,
                    **thread_kwargs,
                )
                buf.message_id = sent.message_id
                buf.last_edit = now
            except Exception as e:
<<<<<<< HEAD
                logger.warning("Stream initial send failed: {}", e)
                raise
=======
                self.logger.warning("Stream initial send failed: {}", e)
                raise  # Let ChannelManager handle retry
>>>>>>> origin/main
        elif (now - buf.last_edit) >= self.config.stream_edit_interval:
            if len(buf.text) > TELEGRAM_MAX_MESSAGE_LEN:
                await self._flush_stream_overflow(int_chat_id, buf, thread_kwargs)
                buf.last_edit = now
                return
            preview = _strip_md_block(buf.text)
            try:
                await self._call_with_retry(
                    self._app.bot.edit_message_text,
                    chat_id=int_chat_id,
                    message_id=buf.message_id,
                    text=preview,
                )
                buf.last_edit = now
<<<<<<< HEAD
            except Exception:
                pass
=======
            except Exception as e:
                if self._is_not_modified_error(e):
                    buf.last_edit = now
                    return
                self.logger.warning("Stream edit failed: {}", e)
                raise  # Let ChannelManager handle retry
>>>>>>> origin/main

    async def _flush_stream_overflow(
        self,
        chat_id: int,
        buf: "_StreamBuf",
        thread_kwargs: dict,
    ) -> None:
        """Split an oversized stream buffer mid-flight.

        Edits the current stream message with the first chunk, sends any
        intermediate chunks as standalone messages, then opens a new message
        for the tail so subsequent deltas continue streaming into it.
        """
        chunks = split_message(buf.text, TELEGRAM_MAX_MESSAGE_LEN)
        if len(chunks) <= 1:
            return
        try:
            await self._call_with_retry(
                self._app.bot.edit_message_text,
                chat_id=chat_id,
                message_id=buf.message_id,
                text=chunks[0],
            )
        except Exception as e:
            if not self._is_not_modified_error(e):
                self.logger.warning("Stream overflow edit failed: {}", e)
                raise
        for chunk in chunks[1:-1]:
            await self._call_with_retry(
                self._app.bot.send_message,
                chat_id=chat_id,
                text=chunk,
                **thread_kwargs,
            )
        tail = chunks[-1]
        sent = await self._call_with_retry(
            self._app.bot.send_message,
            chat_id=chat_id,
            text=tail,
            **thread_kwargs,
        )
        buf.message_id = sent.message_id
        buf.text = tail

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        if not self.is_allowed(self._sender_id(user)):
            return
        await update.message.reply_text(
            f"👋 Hi {user.first_name}! I'm nanobot.\n\n"
            "Send me a message and I'll respond!\n"
            "Type /help to see available commands."
        )

    async def _on_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command for allowed users only."""
        if not update.message or not update.effective_user:
            return
        if not self.is_allowed(self._sender_id(update.effective_user)):
            return
        await update.message.reply_text(
            "🐈 nanobot commands:\n"
            "/new — Start a new conversation\n"
            "/stop — Stop the current task\n"
            "/dream — Trigger dream memory processing\n"
            "/dream-log — Show latest dream diff\n"
            "/dream-restore — Restore a dream snapshot\n"
            "/model — Show or switch the LLM model\n"
            "/tts — Control TTS settings (on/off, voice, provider)\n"
            "/trace — Toggle agent trace output (on/off/status)\n"
            "/stats — Show token usage statistics\n"
            "/stats topic — Show token usage for this topic\n"
            "/restart — Restart the bot\n"
            "/status — Show bot status\n"
            "/help — Show available commands"
        )

    async def _on_tts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tts command for controlling TTS settings."""
        if not update.message or not update.effective_user:
            return

        chat_id = str(update.effective_message.chat_id)
        thread_id = self._get_thread_id(update.effective_message)
        scope_key = self._tts_scope_key(chat_id, thread_id)
        user_id = str(update.effective_user.id)

        # Check if user is allowed
        if not self.is_allowed(self._sender_id(update.effective_user)):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return

        # Parse command arguments
        args = context.args if context.args else []

        def _tts_status_msg(scope_key: str, extra: str = "") -> str:
            override = self._chat_tts_overrides.get(scope_key, {})
            enabled = override.get("enabled", self.tts_manager.config.enabled)
            provider = override.get("provider", self.tts_manager.config.provider)
            voice = override.get("voice", self.tts_manager.config.voice)
            return (
                f"🔊 TTS Settings:\n"
                f"Enabled: {'✅' if enabled else '❌'}\n"
                f"Provider: {provider}\n"
                f"Voice: {voice}" + (f"\n\n{extra}" if extra else "")
            )

        if not args:
            await update.message.reply_text(
                _tts_status_msg(
                    scope_key,
                    "Usage:\n"
                    "/tts on — Enable TTS\n"
                    "/tts off — Disable TTS\n"
                    "/tts voices [locale] — List available voices\n"
                    "/tts voice [name] — Change voice\n"
                    "/tts provider [edge/openai/riva] — Change provider\n"
                    "/tts status — Show current settings",
                )
            )
            return

        command = args[0].lower()

        if command == "on":
            if scope_key not in self._chat_tts_overrides:
                self._chat_tts_overrides[scope_key] = {}
            self._chat_tts_overrides[scope_key]["enabled"] = True
            save_tts_overrides(self._chat_tts_overrides)
            await update.message.reply_text("🔊 TTS enabled for this chat/topic.")

        elif command == "off":
            if scope_key not in self._chat_tts_overrides:
                self._chat_tts_overrides[scope_key] = {}
            self._chat_tts_overrides[scope_key]["enabled"] = False
            save_tts_overrides(self._chat_tts_overrides)
            await update.message.reply_text("🔇 TTS disabled for this chat/topic.")

        elif command == "status":
            await update.message.reply_text(_tts_status_msg(scope_key))

        elif command == "voices":
            # List available voices for current provider, with optional locale filter
            # Usage: /tts voices [locale_filter]  e.g. /tts voices en-US
            override = self._chat_tts_overrides.get(scope_key, {})
            provider_name = override.get("provider", self.tts_manager.config.provider)
            current_voice = override.get("voice", self.tts_manager.config.voice)
            locale_filter = args[1].lower() if len(args) > 1 else None

            await update.message.reply_text(f"⏳ Fetching voices for {provider_name}...")

            try:
                result = await self.tts_manager.get_supported_voices(provider_name)
                voices = result.get("voices", [])

                if not voices:
                    await update.message.reply_text(
                        "❌ No voices available or provider unreachable."
                    )
                    return

                if provider_name == "edge":
                    # Edge has hundreds of voices — filter by locale
                    if locale_filter:
                        voices = [v for v in voices if locale_filter in v.get("locale", "").lower()]
                    else:
                        # Default: match locale of current voice (e.g. "en-US" from "en-US-AriaNeural")
                        parts = current_voice.split("-")
                        default_locale = (
                            f"{parts[0]}-{parts[1]}".lower() if len(parts) >= 2 else "en-us"
                        )
                        voices = [
                            v for v in voices if default_locale in v.get("locale", "").lower()
                        ]

                    if not voices:
                        await update.message.reply_text(
                            f"No voices found for that locale.\n"
                            f"Try: /tts voices en-US  or  /tts voices zh-CN"
                        )
                        return

                    lines = [f"🎙️ Voices ({voices[0].get('locale', '')} — use /tts voice [name]):"]
                    for v in voices[:20]:  # cap at 20 to avoid flood
                        marker = " ✅" if v["name"] == current_voice else ""
                        gender = v.get("gender", "")
                        icon = "👩" if "Female" in gender else "👨" if "Male" in gender else "🎤"
                        lines.append(f"{icon} {v['name']}{marker}")
                    if len(voices) > 20:
                        lines.append(
                            f"… and {len(voices) - 20} more. Narrow with /tts voices en-US"
                        )
                else:
                    # Riva / OpenAI — filter and paginate if needed
                    if locale_filter:
                        voices = [v for v in voices if locale_filter in v.get("locale", "").lower()]

                    # For Riva with many voices, group by base voice (without emotion)
                    if provider_name == "riva" and len(voices) > 30:
                        # Group by base voice name (without emotion)
                        base_voices = {}
                        for v in voices:
                            # Extract base name: "Magpie-Multilingual.EN-US.Mia.Happy" -> "EN-US.Mia"
                            name = v["name"]
                            # Remove prefix and emotion
                            if "Magpie-Multilingual." in name:
                                name = name.replace("Magpie-Multilingual.", "")

                            name_parts = name.rsplit(".", 1)
                            base_name = (
                                name_parts[0]
                                if len(name_parts) > 1
                                and name_parts[1]
                                in [
                                    "Neutral",
                                    "Calm",
                                    "Angry",
                                    "Happy",
                                    "Sad",
                                    "Fearful",
                                    "Disgust",
                                    "PleasantSurprised",
                                    "Disgusted",
                                ]
                                else name
                            )

                            if base_name not in base_voices:
                                base_voices[base_name] = []
                            base_voices[base_name].append(v)

                        # Show base voices with available emotions
                        lines = [f"🎙️ Riva Magpie Voices"]
                        lines.append(f"💡 Filter: /tts voices en-us")
                        lines.append(
                            f"💡 Set voice: /tts voice Magpie-Multilingual.EN-US.Mia.Happy\n"
                        )

                        for base_name in sorted(base_voices.keys())[:15]:
                            variants = base_voices[base_name]
                            marker = (
                                " ✅" if any(v["name"] == current_voice for v in variants) else ""
                            )
                            gender = variants[0].get("gender", "")
                            icon = (
                                "👩" if "Female" in gender else "👨" if "Male" in gender else "🎤"
                            )

                            # Collect emotions for this voice
                            emotions = [v.get("emotion") for v in variants if v.get("emotion")]

                            lines.append(f"{icon} {base_name}{marker}")
                            if emotions:
                                lines.append(f"   🎭 {' · '.join(emotions)}")

                        if len(base_voices) > 15:
                            lines.append(f"\n+{len(base_voices) - 15} more (use locale filter)")
                    else:
                        # Small list, show all
                        lines = [f"🎙️ Available voices (use /tts voice [name]):"]
                        for v in voices[:30]:  # Cap at 30
                            marker = " ✅" if v["name"] == current_voice else ""
                            gender = v.get("gender", "")
                            icon = (
                                "👩" if "Female" in gender else "👨" if "Male" in gender else "🎤"
                            )
                            # Shorten name for display
                            display_name = v["name"].replace("Magpie-Multilingual.", "")
                            lines.append(f"{icon} {display_name}{marker}")

                        if len(voices) > 30:
                            lines.append(f"\n+{len(voices) - 30} more")

                await update.message.reply_text("\n".join(lines))

            except Exception as e:
                logger.error("Failed to list voices: {}", e)
                await update.message.reply_text("❌ Failed to fetch voices.")

        elif command == "voice" and len(args) > 1:
            # Change voice
            new_voice = args[1]
            if scope_key not in self._chat_tts_overrides:
                self._chat_tts_overrides[scope_key] = {}
            self._chat_tts_overrides[scope_key]["voice"] = new_voice
            save_tts_overrides(self._chat_tts_overrides)
            await update.message.reply_text(f"🎙️ Voice changed to: {new_voice}")

        elif command == "provider" and len(args) > 1:
            # Change provider
            new_provider = args[1].lower()
            if new_provider in ["edge", "openai", "riva"]:
                if scope_key not in self._chat_tts_overrides:
                    self._chat_tts_overrides[scope_key] = {}
                self._chat_tts_overrides[scope_key]["provider"] = new_provider
                save_tts_overrides(self._chat_tts_overrides)
                await update.message.reply_text(f"🔄 TTS provider changed to: {new_provider}")
            else:
                await update.message.reply_text(
                    "❌ Invalid provider. Use 'edge', 'openai', or 'riva'."
                )
        else:
            await update.message.reply_text(
                "❓ Unknown command. Usage:\n"
                "/tts on — Enable TTS\n"
                "/tts off — Disable TTS\n"
                "/tts voices [locale] — List available voices\n"
                "/tts voice [name] — Change voice\n"
                "/tts provider [edge/openai/riva] — Change provider\n"
                "/tts status — Show current settings"
            )

    async def _on_trace_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /trace on|off|status command."""
        if not update.message or not update.effective_user:
            return

        chat_id_str = str(update.effective_message.chat_id)
        user_id = str(update.effective_user.id)

        # Check if user is allowed
        if not self.is_allowed(self._sender_id(update.effective_user)):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return

        # Parse command arguments
        args = context.args if context.args else []

        if not args:
            status = "on" if self._trace_enabled.get(chat_id_str, False) else "off"
            await update.message.reply_text(
                f"🔍 Trace mode: {status}\n\nUsage:\n/trace on — Show intermediate thoughts\n/trace off — Hide intermediate thoughts\n/trace status — Show current status"
            )
            return

        command = args[0].lower()

        if command == "on":
            self._trace_enabled[chat_id_str] = True
            await update.message.reply_text(
                "🔍 Trace mode **enabled** for this chat.\nIntermediate thoughts will now appear prefixed with 🤖"
            )
        elif command == "off":
            self._trace_enabled[chat_id_str] = False
            await update.message.reply_text(
                "🔍 Trace mode **disabled** for this chat.\nIntermediate thoughts will be hidden (only shown in logs)."
            )
        elif command == "status":
            status = "on" if self._trace_enabled.get(chat_id_str, False) else "off"
            await update.message.reply_text(
                f"🔍 Trace mode is currently **{status}** for this chat."
            )
        else:
            await update.message.reply_text(
                "❓ Unknown command. Usage:\n"
                "/trace on — Show intermediate thoughts\n"
                "/trace off — Hide intermediate thoughts\n"
                "/trace status — Show current status"
            )

    @staticmethod
    def _sender_id(user) -> str:
        """Build sender_id with username for allowlist matching."""
        sid = str(user.id)
        return f"{sid}|{user.username}" if user.username else sid

    @staticmethod
    def _derive_topic_session_key(message) -> str | None:
        """Derive topic-scoped session key for non-private Telegram chats."""
        message_thread_id = getattr(message, "message_thread_id", None)
        if message_thread_id is None:
            return None
        return f"telegram:{message.chat_id}:topic:{message_thread_id}"

    @staticmethod
    def _get_thread_id(message) -> int | None:
        """Extract the Telegram topic thread id if present."""
        return getattr(message, "message_thread_id", None)

    def _resolve_debounce_lane(self, message) -> str:
        """Scope debounce buffering by chat + topic."""
        return f"{message.chat_id}:{self._get_thread_id(message)}"

    @staticmethod
    def _build_message_metadata(message, user) -> dict:
        """Build common Telegram inbound metadata payload."""
        reply_to = getattr(message, "reply_to_message", None)
        return {
            "message_id": message.message_id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "is_group": message.chat.type != "private",
            "message_thread_id": getattr(message, "message_thread_id", None),
            "is_forum": bool(getattr(message.chat, "is_forum", False)),
            "reply_to_message_id": getattr(reply_to, "message_id", None) if reply_to else None,
        }

    async def _extract_reply_context(self, message) -> str | None:
        """Extract text from the message being replied to, if any."""
        reply = getattr(message, "reply_to_message", None)
        if not reply:
            return None
        text = getattr(reply, "text", None) or getattr(reply, "caption", None) or ""
        if len(text) > TELEGRAM_REPLY_CONTEXT_MAX_LEN:
            text = text[:TELEGRAM_REPLY_CONTEXT_MAX_LEN] + "..."

        if not text:
            return None

        bot_id, _ = await self._ensure_bot_identity()
        reply_user = getattr(reply, "from_user", None)

        if bot_id and reply_user and getattr(reply_user, "id", None) == bot_id:
            return f"[Reply to bot: {text}]"
        elif reply_user and getattr(reply_user, "username", None):
            return f"[Reply to @{reply_user.username}: {text}]"
        elif reply_user and getattr(reply_user, "first_name", None):
            return f"[Reply to {reply_user.first_name}: {text}]"
        else:
            return f"[Reply to: {text}]"

    async def _download_message_media(
        self, msg, *, add_failure_content: bool = False
    ) -> tuple[list[str], list[str]]:
        """Download media from a message (current or reply). Returns (media_paths, content_parts)."""
        media_file = None
        media_type = None
        if getattr(msg, "photo", None):
            media_file = msg.photo[-1]
            media_type = "image"
        elif getattr(msg, "voice", None):
            media_file = msg.voice
            media_type = "voice"
        elif getattr(msg, "audio", None):
            media_file = msg.audio
            media_type = "audio"
        elif getattr(msg, "document", None):
            media_file = msg.document
            media_type = "file"
        elif getattr(msg, "video", None):
            media_file = msg.video
            media_type = "video"
        elif getattr(msg, "video_note", None):
            media_file = msg.video_note
            media_type = "video"
        elif getattr(msg, "animation", None):
            media_file = msg.animation
            media_type = "animation"
        if not media_file or not self._app:
            return [], []
        try:
            file = await self._app.bot.get_file(media_file.file_id)
            ext = self._get_extension(
                media_type,
                getattr(media_file, "mime_type", None),
                getattr(media_file, "file_name", None),
            )
            media_dir = get_media_dir("telegram")
            unique_id = getattr(media_file, "file_unique_id", media_file.file_id)
            file_path = media_dir / f"{unique_id}{ext}"
            await file.download_to_drive(str(file_path))
            path_str = str(file_path)
            if media_type in ("voice", "audio"):
                transcription = await self.transcribe_audio(file_path)
                if transcription:
                    self.logger.info("Transcribed {}: {}...", media_type, transcription[:50])
                    return [path_str], [f"[transcription: {transcription}]"]
                return [path_str], [f"[{media_type}: {path_str}]"]
            return [path_str], [f"[{media_type}: {path_str}]"]
        except Exception as e:
            self.logger.warning("Failed to download message media: {}", e)
            if add_failure_content:
                return [], [f"[{media_type}: download failed]"]
            return [], []

    async def _ensure_bot_identity(self) -> tuple[int | None, str | None]:
        """Load bot identity once and reuse it for mention/reply checks."""
        if self._bot_user_id is not None or self._bot_username is not None:
            return self._bot_user_id, self._bot_username
        if not self._app:
            return None, None
        bot_info = await self._app.bot.get_me()
        self._bot_user_id = getattr(bot_info, "id", None)
        self._bot_username = getattr(bot_info, "username", None)
        return self._bot_user_id, self._bot_username

    @staticmethod
    def _has_mention_entity(
        text: str,
        entities,
        bot_username: str,
        bot_id: int | None,
    ) -> bool:
        """Check Telegram mention entities against the bot username."""
        handle = f"@{bot_username}".lower()
        for entity in entities or []:
            entity_type = getattr(entity, "type", None)
            if entity_type == "text_mention":
                user = getattr(entity, "user", None)
                if user is not None and bot_id is not None and getattr(user, "id", None) == bot_id:
                    return True
                continue
            if entity_type != "mention":
                continue
            offset = getattr(entity, "offset", None)
            length = getattr(entity, "length", None)
            if offset is None or length is None:
                continue
            if text[offset : offset + length].lower() == handle:
                return True
        return handle in text.lower()

    async def _is_group_message_for_bot(self, message) -> bool:
        """Allow group messages when policy is open, @mentioned, or replying to the bot."""
        if message.chat.type == "private" or self.config.group_policy == "open":
            return True

        bot_id, bot_username = await self._ensure_bot_identity()
        if bot_username:
            text = message.text or ""
            caption = message.caption or ""
            if self._has_mention_entity(
                text,
                getattr(message, "entities", None),
                bot_username,
                bot_id,
            ):
                return True
            if self._has_mention_entity(
                caption,
                getattr(message, "caption_entities", None),
                bot_username,
                bot_id,
            ):
                return True

        reply_user = getattr(getattr(message, "reply_to_message", None), "from_user", None)
        return bool(bot_id and reply_user and reply_user.id == bot_id)

    def _remember_thread_context(self, message) -> None:
        """Cache topic thread id by chat/message id for follow-up replies."""
        message_thread_id = getattr(message, "message_thread_id", None)
        if message_thread_id is None:
            return
        key = (str(message.chat_id), message.message_id)
        self._message_threads[key] = message_thread_id
        if len(self._message_threads) > 1000:
            self._message_threads.pop(next(iter(self._message_threads)))

    @staticmethod
<<<<<<< HEAD
    def _has_current_media(message) -> bool:
        return any(
            getattr(message, attr, None)
            for attr in ("photo", "voice", "audio", "document", "video", "video_note", "animation")
        )

    @staticmethod
    def _looks_like_command(content: str) -> bool:
        stripped = re.sub(r"^@\S+\s*", "", (content or "").strip())
        return stripped.startswith("/")

    def _extract_local_command(self, content: str) -> tuple[str, list[str]] | None:
        """Parse Telegram-local commands from raw text or @mention-prefixed text."""
        stripped = re.sub(r"^@\S+\s*", "", (content or "").strip())
        if not stripped.startswith("/"):
            return None
        parts = stripped.split()
        if not parts:
            return None
        command = parts[0][1:].split("@", 1)[0].lower()
        if command not in {"tts", "trace", "stats"}:
            return None
        return command, parts[1:]

    async def _dispatch_local_command(self, update: Update, command: str, args: list[str]) -> bool:
        """Run Telegram-local command handlers outside the agent loop."""
        context = type("TelegramLocalCommandContext", (), {"args": args})()
        if command == "tts":
            await self._on_tts_command(update, context)
            return True
        if command == "trace":
            await self._on_trace_command(update, context)
            return True
        if command == "stats":
            await self._on_stats_command(update, context)
            return True
        return False

    def _find_media_group_buffer(self, lane: str) -> dict[str, Any] | None:
        for buf in self._media_group_buffers.values():
            if buf.get("lane") == lane:
                return buf
        return None

    @staticmethod
    def _merge_debounce_content(companion: str | None, forward: str | None) -> str:
        parts = [part for part in (companion, forward) if part and part != "[empty message]"]
        return "\n\n".join(parts) if parts else "[empty message]"

    def _store_debounce_task(self, lane: str) -> None:
        buf = self._debounce_buffers[lane]
        task = buf.get("task")
        if task and not task.done():
            return
        buf["task"] = asyncio.create_task(self._flush_debounce(lane))

    async def _enqueue_debounce(
        self,
        lane: str,
        *,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str],
        metadata: dict[str, Any],
        session_key: str | None,
        is_forward: bool,
        companion_text: str | None = None,
    ) -> None:
        buf = self._debounce_buffers.setdefault(lane, {})

        if is_forward:
            buf["forward"] = {
                "sender_id": sender_id,
                "chat_id": chat_id,
                "content": content,
                "media": list(dict.fromkeys(media)),
                "metadata": metadata,
                "session_key": session_key,
            }
            if companion_text:
                buf["companion"] = {
                    "sender_id": sender_id,
                    "chat_id": chat_id,
                    "content": companion_text,
                    "media": [],
                    "metadata": metadata,
                    "session_key": session_key,
                }
        else:
            buf["companion"] = {
                "sender_id": sender_id,
                "chat_id": chat_id,
                "content": content,
                "media": list(dict.fromkeys(media)),
                "metadata": metadata,
                "session_key": session_key,
            }

        self._store_debounce_task(lane)

    async def _flush_debounce(self, lane: str) -> None:
        await asyncio.sleep(FORWARD_DEBOUNCE_MS / 1000)
        current = asyncio.current_task()
        buf = self._debounce_buffers.get(lane)
        if not buf or buf.get("task") is not current:
            return

        self._debounce_buffers.pop(lane, None)
        forward = buf.get("forward")
        companion = buf.get("companion")
        payload = companion or forward
        if not payload:
            return

        content = payload["content"]
        media = payload["media"]
        metadata = payload["metadata"]
        session_key = payload["session_key"]
        sender_id = payload["sender_id"]
        chat_id = payload["chat_id"]

        if forward:
            content = self._merge_debounce_content(
                companion["content"] if companion else None,
                forward["content"],
            )
            media = list(
                dict.fromkeys(
                    (forward.get("media") or [])
                    + (companion.get("media") or [] if companion else [])
                )
            )
            metadata = {**forward["metadata"], **(companion["metadata"] if companion else {})}
            session_key = (
                companion["session_key"]
                if companion and companion.get("session_key") is not None
                else forward["session_key"]
            )
            sender_id = companion["sender_id"] if companion else forward["sender_id"]
            chat_id = companion["chat_id"] if companion else forward["chat_id"]

        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=media,
            metadata=metadata,
            session_key=session_key,
        )
=======
    def _queue_key_for_message(message) -> str:
        """Return the final nanobot session key used for ordered Telegram ingress."""
        return TelegramChannel._derive_topic_session_key(message) or f"telegram:{message.chat_id}"

    @staticmethod
    def _sort_key_for_update(update: Update) -> tuple[int, int]:
        """Sort by chat message id first, then Telegram update id."""
        message = getattr(update, "message", None)
        message_id = int(getattr(message, "message_id", 0) or 0)
        update_id = int(getattr(update, "update_id", 0) or 0)
        return (message_id, update_id)

    def _enqueue_ordered_update(
        self,
        *,
        kind: Literal["command", "message"],
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Stage a Telegram update behind a short per-session reorder window."""
        message = update.message
        key = self._queue_key_for_message(message)
        self._inbound_buffers.setdefault(key, []).append(
            _QueuedTelegramUpdate(
                kind=kind,
                update=update,
                context=context,
                sort_key=self._sort_key_for_update(update),
            )
        )
        if key not in self._inbound_workers:
            self._inbound_workers[key] = asyncio.create_task(
                self._drain_ordered_updates(key)
            )

    async def _drain_ordered_updates(self, key: str) -> None:
        """Drain one Telegram session buffer in stable message order."""
        try:
            while self._running:
                await asyncio.sleep(0.2)
                batch = self._inbound_buffers.get(key, [])
                if not batch:
                    break
                self._inbound_buffers[key] = []
                batch.sort(key=lambda item: item.sort_key)
                for item in batch:
                    try:
                        if item.kind == "command":
                            await self._process_forward_command(item.update, item.context)
                        else:
                            await self._process_message_update(item.update, item.context)
                    except Exception as e:
                        self.logger.warning(
                            "Telegram queued update handling failed for {}: {}",
                            key,
                            e,
                        )
            if not self._inbound_buffers.get(key):
                self._inbound_buffers.pop(key, None)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.logger.warning("Telegram ordered update worker failed for {}: {}", key, e)
        finally:
            if not self._inbound_buffers.get(key):
                self._inbound_workers.pop(key, None)
>>>>>>> origin/main

    async def _forward_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Forward slash commands (private chats only) to the bus for handling in AgentLoop."""
        if not update.message or not update.effective_user:
            return
        if not self._running:
            await self._process_forward_command(update, context)
            return
        self._enqueue_ordered_update(kind="command", update=update, context=context)

    async def _process_forward_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process a queued slash command."""
        message = update.message
        user = update.effective_user
        sender_id = self._sender_id(user)
        if not self.is_allowed(sender_id):
            return
        self._remember_thread_context(message)
        text = message.text or ""
        if text.startswith("/"):
            parts = text.split(None, 1)
            command = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            if "@" in command:
                command = command.split("@", 1)[0]
            text = f"{command} {rest}".strip()
        text = self._normalize_telegram_command(text)
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str(message.chat_id),
            content=text,
            metadata=self._build_message_metadata(message, user),
            session_key=self._derive_topic_session_key(message),
            is_dm=message.chat.type == "private",
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages (text, photos, voice, documents)."""
        if not update.message or not update.effective_user:
            return
        if not self._running:
            await self._process_message_update(update, context)
            return
        self._enqueue_ordered_update(kind="message", update=update, context=context)

    async def _process_message_update(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Process a queued Telegram message update."""

        message = update.message
        user = update.effective_user
        chat_id = message.chat_id
        sender_id = self._sender_id(user)
<<<<<<< HEAD
        is_group = message.chat.type != "private"

=======
        if not self.is_allowed(sender_id):
            return
>>>>>>> origin/main
        self._remember_thread_context(message)

        # Check group_policy for group chats
        if not await self._is_group_message_for_bot(message):
            logger.debug("Ignoring group message - bot not mentioned (group_policy=mention)")
            return

        # Capture topic thread_id for topic-aware routing
        thread_id = self._get_thread_id(message)
        lane = self._resolve_debounce_lane(message)

        # Add ACK reaction to acknowledge message receipt
        await self._add_ack_reaction(chat_id, message.message_id)

        # Send thinking message for private chats only
        await self._send_thinking_message(chat_id, is_group, thread_id)

        # Build content from text and/or media
        content_parts = []
        media_paths = []

        # Text content
        if message.text:
            content_parts.append(str(message.text))
        if message.caption:
            content_parts.append(str(message.caption))
        location = getattr(message, "location", None)
        if location is not None:
            content_parts.append(f"[location: {location.latitude}, {location.longitude}]")

        # Download current message media
        current_media_paths, current_media_parts = await self._download_message_media(
            message, add_failure_content=True
        )
        media_paths.extend(current_media_paths)
        content_parts.extend(current_media_parts)
        if current_media_paths:
            self.logger.debug("Downloaded message media to {}", current_media_paths[0])

        # Reply context: text and/or media from the replied-to message
        reply = getattr(message, "reply_to_message", None)
        if reply is not None:
            reply_ctx = await self._extract_reply_context(message)
            reply_media, reply_media_parts = await self._download_message_media(reply)
            if reply_media:
                media_paths = reply_media + media_paths
<<<<<<< HEAD
                logger.debug("Attached replied-to media: {}", reply_media[0])
            tag = reply_ctx or (
                f"[Reply to: {reply_media_parts[0]}]" if reply_media_parts else None
            )
=======
                self.logger.debug("Attached replied-to media: {}", reply_media[0])
            tag = reply_ctx or (f"[Reply to: {reply_media_parts[0]}]" if reply_media_parts else None)
>>>>>>> origin/main
            if tag:
                content_parts.insert(0, tag)
        content = "\n".join(content_parts) if content_parts else "[empty message]"

        self.logger.debug("message from {}: {}...", sender_id, content[:50])

        str_chat_id = str(chat_id)
        comp_key = self._composite_key(str_chat_id, thread_id)

        # Build metadata including thread_id for topic support
        msg_metadata = self._build_message_metadata(message, user)

        if local_command := self._extract_local_command(content):
            command, args = local_command
            await self._dispatch_local_command(update, command, args)
            return

        # Telegram media groups: buffer briefly, forward as one aggregated turn.
        if media_group_id := getattr(message, "media_group_id", None):
            key = f"{str_chat_id}:{media_group_id}"
            if key not in self._media_group_buffers:
                companion_text = None
                if pending := self._debounce_buffers.pop(lane, None):
                    task = pending.get("task")
                    if task and not task.done():
                        task.cancel()
                    companion = pending.get("companion")
                    if companion and not pending.get("forward"):
                        companion_text = companion.get("content")
                self._media_group_buffers[key] = {
                    "sender_id": sender_id,
                    "chat_id": str_chat_id,
                    "contents": [],
                    "media": [],
                    "metadata": msg_metadata,
                    "lane": lane,
                    "is_forward": bool(getattr(message, "forward_origin", None)),
                    "session_key": self._derive_topic_session_key(message),
                    "companion_text": companion_text,
                }
                try:
                    self._start_typing(comp_key, thread_id)
                except TypeError:
                    self._start_typing(comp_key)
                await self._add_reaction(str_chat_id, message.message_id, self.config.react_emoji)
            buf = self._media_group_buffers[key]
            if content and content != "[empty message]":
                buf["contents"].append(content)
            buf["media"].extend(media_paths)
            if key not in self._media_group_tasks:
                self._media_group_tasks[key] = asyncio.create_task(self._flush_media_group(key))
            return

        # Start typing indicator before processing
        try:
            self._start_typing(comp_key, thread_id)
        except TypeError:
            self._start_typing(comp_key)
        await self._add_reaction(str_chat_id, message.message_id, self.config.react_emoji)

        # Scope session per topic to isolate conversation context
        session_key = self._derive_topic_session_key(message)

        if self._looks_like_command(content):
            await self._handle_message(
                sender_id=sender_id,
                chat_id=str_chat_id,
                content=content,
                media=media_paths,
                metadata=msg_metadata,
                session_key=session_key,
            )
            return

        if existing_media_group := self._find_media_group_buffer(lane):
            if content and content != "[empty message]":
                existing_media_group["companion_text"] = self._merge_debounce_content(
                    existing_media_group.get("companion_text"),
                    content,
                )
            return

        if not getattr(message, "media_group_id", None):
            await self._handle_message(
                sender_id=sender_id,
                chat_id=str_chat_id,
                content=content,
                media=media_paths,
                metadata=msg_metadata,
                session_key=session_key,
            )
            return

        is_forward = bool(getattr(message, "forward_origin", None))
        if is_forward or not self._has_current_media(message):
            existing = self._debounce_buffers.get(lane)
            if existing and existing.get("forward") and content and content != "[empty message]":
                existing["companion"] = {
                    "sender_id": sender_id,
                    "chat_id": str_chat_id,
                    "content": content,
                    "media": media_paths,
                    "metadata": msg_metadata,
                    "session_key": session_key,
                }
                return
            await self._enqueue_debounce(
                lane,
                sender_id=sender_id,
                chat_id=str_chat_id,
                content=content,
                media=media_paths,
                metadata=msg_metadata,
                session_key=session_key,
                is_forward=is_forward,
            )
            return

        # Forward to the message bus
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str_chat_id,
            content=content,
            media=media_paths,
            metadata=msg_metadata,
            session_key=session_key,
        )

    async def _flush_media_group(self, key: str) -> None:
        """Wait briefly, then forward buffered media-group as one turn."""
        try:
            await asyncio.sleep(0.6)
            if not (buf := self._media_group_buffers.pop(key, None)):
                return
            content = "\n".join(buf["contents"]) or "[empty message]"
            if buf.get("is_forward"):
                await self._enqueue_debounce(
                    buf["lane"],
                    sender_id=buf["sender_id"],
                    chat_id=buf["chat_id"],
                    content=content,
                    media=list(dict.fromkeys(buf["media"])),
                    metadata=buf["metadata"],
                    session_key=buf.get("session_key"),
                    is_forward=True,
                    companion_text=buf.get("companion_text"),
                )
            else:
                content = self._merge_debounce_content(buf.get("companion_text"), content)
                await self._handle_message(
                    sender_id=buf["sender_id"],
                    chat_id=buf["chat_id"],
                    content=content,
                    media=list(dict.fromkeys(buf["media"])),
                    metadata=buf["metadata"],
                    session_key=buf.get("session_key"),
                )
        finally:
            self._media_group_tasks.pop(key, None)

    async def _add_ack_reaction(self, chat_id: int, message_id: int) -> None:
        """Add a random emoji reaction to acknowledge message receipt (non-blocking)."""
        if not self._app:
            return

        try:
            react = self.config.react_emoji
            if isinstance(react, list):
                react = [emoji for emoji in react if isinstance(emoji, str) and emoji]
                if not react:
                    return
                import random

                emoji = random.choice(react)
            else:
                emoji = react if isinstance(react, str) else ""
                if not emoji:
                    return
            if HAS_REACTION_TYPE:
                await self._app.bot.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[ReactionTypeEmoji(emoji)],
                    is_big=False,
                )
            else:
                # Fallback for older versions
                await self._app.bot.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[{"type": "emoji", "emoji": emoji}],
                    is_big=False,
                )
            logger.debug("Added ACK reaction {} to message {}", emoji, message_id)
        except Exception as e:
            # Reactions might not be supported in all chats, so just log at debug level
            logger.debug("Failed to add ACK reaction to message {}: {}", message_id, e)

    async def _send_thinking_message(
        self,
        chat_id: int,
        is_group: bool,
        thread_id: int | None = None,
    ) -> None:
        """Send a 'Thinking...' placeholder message in private chats only."""
        if not self._app or is_group:
            return

        try:
            # Use composite key for both chat_id and thread_id
            comp_key = self._composite_key(str(chat_id), thread_id)
            thread_kwargs: dict = {}
            if thread_id:
                thread_kwargs["message_thread_id"] = thread_id
            thinking_msg = await self._app.bot.send_message(
                chat_id=chat_id,
                text="💭 Thinking...",
                **thread_kwargs,
            )
            self._thinking_messages[comp_key] = thinking_msg.message_id
            logger.debug("Sent thinking message {} to chat {}", thinking_msg.message_id, chat_id)
        except Exception as e:
            logger.debug("Failed to send thinking message: {}", e)

    def _start_typing(self, comp_key: str, thread_id: int | None = None) -> None:
        """Start sending 'typing...' indicator for a chat (optionally in a topic)."""
        self._stop_typing(comp_key)
        self._typing_tasks[comp_key] = asyncio.create_task(self._typing_loop(comp_key, thread_id))

    def _stop_typing(self, comp_key: str) -> None:
        """Stop the typing indicator for a chat/topic."""
        task = self._typing_tasks.pop(comp_key, None)
        if task and not task.done():
            task.cancel()

    async def _add_reaction(self, chat_id: str, message_id: int, emoji: str | list[str]) -> None:
        """Add emoji reaction to a message (best-effort, non-blocking)."""
        if not self._app or not emoji:
            return

        if isinstance(emoji, list):
            emoji = next((item for item in emoji if isinstance(item, str) and item), "")
        elif not isinstance(emoji, str):
            emoji = ""

        if not emoji:
            return
        try:
            await self._app.bot.set_message_reaction(
                chat_id=int(chat_id),
                message_id=message_id,
                reaction=[ReactionTypeEmoji(emoji)],
            )
        except Exception as e:
            self.logger.debug("reaction failed: {}", e)

    async def _remove_reaction(self, chat_id: str, message_id: int) -> None:
        """Remove emoji reaction from a message (best-effort, non-blocking)."""
        if not self._app:
            return
        try:
            await self._app.bot.set_message_reaction(
                chat_id=int(chat_id),
                message_id=message_id,
                reaction=[],
            )
        except Exception as e:
            self.logger.debug("reaction removal failed: {}", e)

    async def _typing_loop(self, comp_key: str, thread_id: int | None = None) -> None:
        """Repeatedly send 'typing' action until cancelled."""
        # Extract the numeric chat_id from the composite key
        raw_chat_id = comp_key.split(":", 1)[0]
        try:
<<<<<<< HEAD
            while self._app:
                kwargs: dict = {"chat_id": int(raw_chat_id), "action": "typing"}
                if thread_id:
                    kwargs["message_thread_id"] = thread_id
                await self._app.bot.send_chat_action(**kwargs)
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("Typing indicator stopped for {}: {}", comp_key, e)
=======
            with suppress(asyncio.CancelledError):
                while self._app:
                    await self._app.bot.send_chat_action(chat_id=int(chat_id), action="typing")
                    await asyncio.sleep(4)
        except Exception as e:
            self.logger.debug("Typing indicator stopped for {}: {}", chat_id, e)
>>>>>>> origin/main

    async def _on_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command to show token usage statistics."""
        if not update.message or not update.effective_user:
            return

<<<<<<< HEAD
        chat_id = str(update.effective_message.chat_id)
        user_id = str(update.effective_user.id)

        # Check if user is allowed
        if not self.is_allowed(self._sender_id(update.effective_user)):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return

        # Parse command arguments
        args = context.args if context.args else []

        try:
            # Import StatsManager to get usage statistics
            from nanobot.utils.stats import StatsManager
            from pathlib import Path

            # Get workspace path
            workspace_path = (
                Path(self._workspace_path)
                if self._workspace_path
                else Path("~/.nanobot/workspace").expanduser()
            )
            stats_manager = StatsManager(workspace_path)

            # Check if topic-specific stats are requested
            if args and args[0].lower() == "topic":
                # Show stats for this specific topic
                message_thread_id = getattr(update.effective_message, "message_thread_id", None)
                if message_thread_id:
                    topic_stats = stats_manager.get_stats(
                        "telegram", f"{chat_id}:topic:{message_thread_id}"
                    )
                    if topic_stats:
                        total_input = topic_stats.get("total_input_tokens", 0)
                        total_output = topic_stats.get("total_output_tokens", 0)
                        total_tokens = topic_stats.get("total_tokens", 0)
                        count = topic_stats.get("count", 0)

                        response = (
                            "📊 <b>Token Usage Statistics (This Topic)</b>\n\n"
                            f"🔢 Requests in this topic: <code>{count}</code>\n"
                            f"📥 Input Tokens: <code>{total_input:,}</code>\n"
                            f"📤 Output Tokens: <code>{total_output:,}</code>\n"
                            f"总计 Tokens: <code>{total_tokens:,}</code>"
                        )
                    else:
                        response = "📊 No token usage statistics found for this topic."
                else:
                    response = "❌ This command is only available in topic threads."
            else:
                # Get statistics
                if args and args[0].lower() == "all":
                    # Show all statistics
                    stats = stats_manager.get_all_stats()
                    if stats:
                        total_input = stats.get("total_input_tokens", 0)
                        total_output = stats.get("total_output_tokens", 0)
                        total_tokens = stats.get("total_tokens", 0)
                        count = stats.get("count", 0)

                        response = (
                            "📊 <b>Total Token Usage Statistics</b>\n\n"
                            f"🔢 Total Requests: <code>{count}</code>\n"
                            f"📥 Input Tokens: <code>{total_input:,}</code>\n"
                            f"📤 Output Tokens: <code>{total_output:,}</code>\n"
                            f"总计 Tokens: <code>{total_tokens:,}</code>"
                        )
                    else:
                        response = "📊 No token usage statistics found."
                else:
                    # Show statistics for this specific channel/chat
                    stats = stats_manager.get_stats("telegram", chat_id)
                    if stats:
                        total_input = stats.get("total_input_tokens", 0)
                        total_output = stats.get("total_output_tokens", 0)
                        total_tokens = stats.get("total_tokens", 0)
                        count = stats.get("count", 0)

                        response = (
                            "📊 <b>Token Usage Statistics (This Chat)</b>\n\n"
                            f"🔢 Requests in this chat: <code>{count}</code>\n"
                            f"📥 Input Tokens: <code>{total_input:,}</code>\n"
                            f"📤 Output Tokens: <code>{total_output:,}</code>\n"
                            f"总计 Tokens: <code>{total_tokens:,}</code>"
                        )
                    else:
                        response = "📊 No token usage statistics found for this chat."

            await update.message.reply_text(response, parse_mode="HTML")

        except Exception as e:
            logger.error("Failed to fetch stats: {}", e)
            await update.message.reply_text("❌ Failed to fetch token usage statistics.")

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log polling / handler errors instead of silently swallowing them."""
        error = context.error
        message = str(error) or error.__class__.__name__
        if error.__class__.__name__ == "NetworkError":
            logger.warning("Telegram network issue: {}", message)
        else:
            logger.error("Telegram error: {}", message)

    def _on_polling_error(self, error: Exception) -> None:
        """PTB polling requires a plain callback, not a coroutine function."""
        message = str(error) or error.__class__.__name__
        if error.__class__.__name__ == "NetworkError":
            logger.warning("Telegram polling network issue: {}", message)
        else:
            logger.error("Telegram polling error: {}", message)
=======
    def _on_polling_error(self, exc: Exception) -> None:
        """Keep long-polling network failures to a single readable line."""
        summary = self._format_telegram_error(exc)
        if isinstance(exc, (NetworkError, TimedOut)):
            self.logger.warning("polling network issue: {}", summary)
        else:
            self.logger.error("polling error: {}", summary)

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log polling / handler errors instead of silently swallowing them."""
        summary = self._format_telegram_error(context.error)

        if isinstance(context.error, (NetworkError, TimedOut)):
            self.logger.warning("network issue: {}", summary)
        else:
            self.logger.error("error: {}", summary)
>>>>>>> origin/main

    def _get_extension(
        self,
        media_type: str,
        mime_type: str | None,
        filename: str | None = None,
    ) -> str:
        """Get file extension based on media type and optional filename."""
        if mime_type:
            ext_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "image/webp": ".webp",
                "audio/ogg": ".ogg",
                "audio/mpeg": ".mp3",
                "audio/mp4": ".m4a",
                "video/mp4": ".mp4",
                "video/quicktime": ".mov",
                "video/webm": ".webm",
                "video/x-matroska": ".mkv", "video/3gpp": ".3gp",
            }
            if mime_type in ext_map:
                return ext_map[mime_type]

        if filename:
            p = Path(filename)
            if p.suffixes:
                # Return full compound extension if present (e.g. .tar.gz)
                return "".join(p.suffixes).lower()
            if p.suffix:
                return p.suffix.lower()

        type_map = {"image": ".jpg", "voice": ".ogg", "audio": ".mp3", "video": ".mp4", "file": ""}
        return type_map.get(media_type, "")

    def _build_keyboard(self, buttons: list) -> InlineKeyboardMarkup | None:
        """Build inline keyboard markup if inline_keyboards is enabled."""
        if not buttons or not self.config.inline_keyboards:
            return None
        keyboard = [
            [InlineKeyboardButton(label, callback_data=self._safe_callback_data(label)) for label in row]
            for row in buttons
        ]
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def _safe_callback_data(label: str) -> str:
        # Telegram caps callback_data at 64 bytes UTF-8; truncate at a char boundary so the keyboard still sends.
        encoded = label.encode("utf-8")
        if len(encoded) <= 64:
            return label
        return encoded[:64].decode("utf-8", errors="ignore")

    @staticmethod
    def _buttons_as_text(buttons: list[list[str]]) -> str:
        # Buttons are semantic options; when we can't render a keyboard, the user still needs to see them.
        return "\n".join(" ".join(f"[{label}]" for label in row) for row in buttons if row)

    async def _on_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline keyboard button clicks (callback queries)."""
        if not update.callback_query or not update.effective_user:
            return
        query = update.callback_query
        user = update.effective_user
        chat_id = query.message.chat_id if query.message else None
        sender_id = self._sender_id(user)
        if not chat_id:
            self.logger.warning("Callback query without chat_id")
            return
        if not self.is_allowed(sender_id):
            return
        button_label = query.data or ""
        await query.answer()
        if query.message:
            with suppress(Exception):
                await query.message.edit_reply_markup(reply_markup=None)
        self.logger.debug("Inline button tap from {}: {}", sender_id, button_label)
        self._start_typing(str(chat_id))
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str(chat_id),
            content=button_label,
            metadata={
                "callback_query_id": query.id,
                "button_label": button_label,
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "is_callback": True,
            },
        )
