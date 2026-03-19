"""Telegram channel implementation using python-telegram-bot."""

from __future__ import annotations

import asyncio
import random
import re
import unicodedata

from loguru import logger
from telegram import BotCommand, ReplyParameters, Update
try:
    from telegram import ReactionTypeEmoji
    HAS_REACTION_TYPE = True
except ImportError:
    HAS_REACTION_TYPE = False
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

from io import BytesIO

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import TelegramConfig
from nanobot.tts.manager import TTSManager
from nanobot.utils.audio import convert_to_ogg_opus, get_audio_duration
from nanobot.utils.helpers import split_message

TELEGRAM_MAX_MESSAGE_LEN = 4000  # Telegram message character limit


# ACK reaction emojis pool
TELEGRAM_ACK_REACTIONS = ["⚡️", "👌", "👀", "🔥", "👍"]


def _random_ack_reaction() -> str:
    """Return a random emoji from the ACK reactions pool."""
    return random.choice(TELEGRAM_ACK_REACTIONS)


def _strip_md(s: str) -> str:
    """Strip markdown inline formatting from text."""
    s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
    s = re.sub(r'__(.+?)__', r'\1', s)
    s = re.sub(r'~~(.+?)~~', r'\1', s)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    return s.strip()


def _render_table_box(table_lines: list[str]) -> str:
    """Convert markdown pipe-table to compact aligned text for <pre> display."""

    def dw(s: str) -> int:
        return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)

    rows: list[list[str]] = []
    has_sep = False
    for line in table_lines:
        cells = [_strip_md(c) for c in line.strip().strip('|').split('|')]
        if all(re.match(r'^:?-+:?$', c) for c in cells if c):
            has_sep = True
            continue
        rows.append(cells)
    if not rows or not has_sep:
        return '\n'.join(table_lines)

    ncols = max(len(r) for r in rows)
    for r in rows:
        r.extend([''] * (ncols - len(r)))
    widths = [max(dw(r[c]) for r in rows) for c in range(ncols)]

    def dr(cells: list[str]) -> str:
        return '  '.join(f'{c}{" " * (w - dw(c))}' for c, w in zip(cells, widths))

    out = [dr(rows[0])]
    out.append('  '.join('─' * w for w in widths))
    for row in rows[1:]:
        out.append(dr(row))
    return '\n'.join(out)


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

    text = re.sub(r'```[\w]*\n?([\s\S]*?)```', save_code_block, text)

    # 1.5. Convert markdown tables to box-drawing (reuse code_block placeholders)
    lines = text.split('\n')
    rebuilt: list[str] = []
    li = 0
    while li < len(lines):
        if re.match(r'^\s*\|.+\|', lines[li]):
            tbl: list[str] = []
            while li < len(lines) and re.match(r'^\s*\|.+\|', lines[li]):
                tbl.append(lines[li])
                li += 1
            box = _render_table_box(tbl)
            if box != '\n'.join(tbl):
                code_blocks.append(box)
                rebuilt.append(f"\x00CB{len(code_blocks) - 1}\x00")
            else:
                rebuilt.extend(tbl)
        else:
            rebuilt.append(lines[li])
            li += 1
    text = '\n'.join(rebuilt)

    # 2. Extract and protect inline code
    inline_codes: list[str] = []
    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r'`([^`]+)`', save_inline_code, text)

    # 3. Headers # Title -> just the title text
    text = re.sub(r'^#{1,6}\s+(.+)$', r'\1', text, flags=re.MULTILINE)

    # 4. Blockquotes > text -> just the text (before HTML escaping)
    text = re.sub(r'^>\s*(.*)$', r'\1', text, flags=re.MULTILINE)

    # 5. Escape HTML special characters
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 6. Links [text](url) - must be before bold/italic to handle nested cases
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    # 7. Bold **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # 7b. Bold *text* (single asterisk) — after ** is consumed
    # Matches *word* and *multi word* but not "* bullet" (asterisk + space at start)
    text = re.sub(r'\*(\S(?:[^*]*\S)?)\*(?!\*)', r'<b>\1</b>', text)

    # 8. Italic _text_ (avoid matching inside words like some_var_name)
    text = re.sub(r'(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])', r'<i>\1</i>', text)

    # 9. Strikethrough ~~text~~
    text = re.sub(r'~~(.+?)~~', r'<s>\1</s>', text)

    # 10. Bullet lists - item -> • item
    text = re.sub(r'^[-*]\s+', '• ', text, flags=re.MULTILINE)

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

    return text


class TelegramChannel(BaseChannel):
    """
    Telegram channel using long polling.

    Simple and reliable - no webhook/public IP needed.
    """

    name = "telegram"

    # Commands registered with Telegram's command menu
    BOT_COMMANDS = [
        BotCommand("start", "Start the bot"),
        BotCommand("new", "Start a new conversation"),
        BotCommand("stop", "Stop the current task"),
        BotCommand("model", "Show or switch the LLM model"),
        BotCommand("tts", "Control TTS settings (on/off, voices, voice, provider)"),
        BotCommand("trace", "Toggle agent trace output (on/off/status)"),
        BotCommand("stats", "Show token usage statistics"),
        BotCommand("help", "Show available commands"),
    ]

    def __init__(
        self,
        config: TelegramConfig,
        bus: MessageBus,
        groq_api_key: str = "",
        workspace_path: str | None = None,
    ):
        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self.groq_api_key = groq_api_key
        self._workspace_path = workspace_path
        self._app: Application | None = None
        self._typing_tasks: dict[str, asyncio.Task] = {}  # composite_key -> typing loop task
        self._thinking_messages: dict[str, int] = {}  # composite_key -> thinking message_id
        self._media_group_buffers: dict[str, dict] = {}
        self._media_group_tasks: dict[str, asyncio.Task] = {}
        self._message_threads: dict[tuple[str, int], int] = {}
        self._bot_user_id: int | None = None
        self._bot_username: str | None = None
        
        # TTS manager initialization
        from nanobot.tts.manager import TTSManager
        self.tts_manager = TTSManager(config.tts)
        
        # Per-chat TTS overrides (for /tts command)
        self._chat_tts_overrides: dict[str, dict] = {}

        # Per-chat trace toggle (runtime-only, resets on restart).
        # When True, intermediate thinking/tool-hint progress messages are
        # forwarded to the chat prefixed with "🤖 ".  Default is False (suppress).
        self._trace_enabled: dict[str, bool] = {}

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

    async def start(self) -> None:
        """Start the Telegram bot with long polling."""
        if not self.config.token:
            logger.error("Telegram bot token not configured")
            return

        self._running = True

        # Build the application with larger connection pool to avoid pool-timeout on long runs
        req = HTTPXRequest(
            connection_pool_size=16,
            pool_timeout=5.0,
            connect_timeout=30.0,
            read_timeout=30.0,
            proxy=self.config.proxy if self.config.proxy else None,
        )
        builder = Application.builder().token(self.config.token).request(req).get_updates_request(req)
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
        self._app.add_handler(CommandHandler("stats", self._on_stats_command, filters=private_only))

        # Add message handler for text, photos极voice, documents.
        # In groups, commands typed as "@BotName /cmd" are plain TEXT (not COMMAND
        # entities from Telegram's perspective when prefixed by a mention), so we
        # include all TEXT here.  The ~filters.COMMAND exclusion only applies
        # private chats where CommandHandlers above take precedence.
        self._app.add_handler(
            MessageHandler(
                (filters.TEXT | filters.PHOTO | filters.VOICE | filters.AUDIO | filters.Document.ALL),
                self._on_message
            )
        )

        logger.info("Starting Telegram bot (polling mode)...")

        # Initialize and start polling
        await self._app.initialize()
        await self._app.start()

        # Get bot info and register command menu
        bot_info = await self._app.bot.get_me()
        self._bot_user_id = getattr(bot_info, "id", None)
        self._bot_username = getattr(bot_info, "username", None)
        logger.info("Telegram bot @{} connected", bot_info.username)

        try:
            await self._app.bot.set_my_commands(self.BOT_COMMANDS)
            logger.debug("Telegram bot commands registered")
        except Exception as e:
            logger.warning("Failed to register bot commands: {}", e)

        # Start polling (this runs until stopped)
        await self._app.updater.start_polling(
            allowed_updates=["message"],
            drop_pending_updates=True  # Ignore old messages on startup
        )

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

        if self._app:
            logger.info("Stopping Telegram bot...")
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
        if ext == "ogg":
            return "voice"
        if ext in ("mp3", "m4a", "wav", "aac"):
            return "audio"
        return "document"

    @staticmethod
    def _composite_key(chat_id: str, thread_id: int | None = None) -> str:
        """Build a composite key for typing/thinking state dicts."""
        return f"{chat_id}:{thread_id}" if thread_id else chat_id

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Telegram."""
        if not self._app:
            logger.warning("Telegram bot not running")
            return

        thread_id = msg.metadata.get("message_thread_id")
        comp_key = self._composite_key(msg.chat_id, thread_id)

        is_progress = msg.metadata.get("_progress", False)

        # Only stop typing indicator for final responses
        if not is_progress:
            self._stop_typing(comp_key)

        try:
            chat_id = int(msg.chat_id)
        except ValueError:
            logger.error("Invalid chat_id: {}", msg.chat_id)
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
            if not trace_on:
                return  # suppressed - only logged

            # Trace enabled → send to chat with prefix
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
                        message_id=reply_to_message_id,
                        allow_sending_without_reply=True
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
            cached_thread_id = self._message_threads.get(
                (msg.chat_id, msg.metadata["message_id"])
            )
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
                    message_id=reply_to_message_id,
                    allow_sending_without_reply=True
                )

        # Send media files
        for media_path in (msg.media or []):
            try:
                media_type = self._get_media_type(media_path)
                sender = {
                    "photo": self._app.bot.send_photo,
                    "voice": self._app.bot.send_voice,
                    "audio": self._app.bot.send_audio,
                }.get(media_type, self._app.bot.send_document)
                param = "photo" if media_type == "photo" else media_type if media_type in ("voice", "audio") else "document"
                with open(media_path, 'rb') as f:
                    await sender(
                        chat_id=chat_id,
                        **{param: f},
                        reply_parameters=reply_params,
                        **thread_kwargs,
                    )
            except Exception as e:
                filename = media_path.rsplit("/", 1)[-1]
                logger.error("Failed to send media {}: {}", media_path, e)
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=f"[Failed to send: {filename}]",
                    reply_parameters=reply_params,
                    **thread_kwargs,
                )

        # TTS voice note (if enabled and we have text content)
        voice_note_sent = False

        # Check if TTS is enabled (considering chat-specific overrides)
        chat_id_str = str(chat_id)
        chat_override = self._chat_tts_overrides.get(chat_id_str, {})
        tts_enabled = chat_override.get("enabled", self.tts_manager.config.enabled)

        # Skip TTS for command responses that should not trigger TTS
        # Check if this is a command response by looking at metadata or content
        is_command_response = False
        if msg.metadata.get("command_response", False):
            is_command_response = True
            logger.debug("Skipping TTS for command response")
        elif msg.content and msg.content.strip():
            # Check if content looks like a command response (starts with command name)
            content_stripped = msg.content.strip()
            if content_stripped.startswith("/model") or content_stripped.startswith("/tts") or content_stripped.startswith("/trace"):
                is_command_response = True
                logger.debug("Skipping TTS for command response (detected from content)")

        if tts_enabled and msg.content and msg.content.strip() and not is_command_response:
            # Skip TTS for messages that look like structured data or errors
            # These are typically cron job, health check, or error messages
            content = msg.content.strip()
            if "|" in content and "---" in content:
                # Table-like structure - likely cron job or health check output
                logger.debug("Skipping TTS for table-like message")
            elif content.startswith("{") and content.endswith("}"):
                # JSON-like object - likely error or structured data
                logger.debug("Skipping TTS for JSON-like message")
            elif content.startswith("[") and content.endswith("]"):
                # JSON array - likely error or structured data
                logger.debug("Skipping TTS for JSON array message")
            elif "Error:" in content and ":" in content:
                # Error message pattern
                logger.debug("Skipping TTS for error message")
            else:
                try:
                    logger.debug("Attempting TTS generation for message")

                    # Apply chat-specific overrides for TTS generation
                    tts_config = self.config.tts.model_copy()
                    if "voice" in chat_override:
                        tts_config.voice = chat_override["voice"]
                    if "provider" in chat_override:
                        tts_config.provider = chat_override["provider"]
                    if "enabled" in chat_override:
                        tts_config.enabled = chat_override["enabled"]

                    # Log effective TTS config for debugging
                    logger.debug(f"TTS effective config: chat_id={chat_id} override=True enabled={tts_config.enabled} provider={tts_config.provider} voice={tts_config.voice}")

                    # Create temporary TTS manager with overridden config
                    from nanobot.tts.manager import TTSManager
                    temp_tts_manager = TTSManager(tts_config)

                    ogg_bytes = await temp_tts_manager.generate_voice_note(msg.content)

                    if ogg_bytes:
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
                        voice_note_sent = True
                        logger.info(f"TTS voice note sent ({duration:.1f}s)")
                    else:
                        logger.warning("TTS returned no audio → skipping voice note")
                except Exception as e:
                    logger.exception("TTS generation or sending failed → falling back to text only")

        # Send text content
        if msg.content and msg.content != "[empty message]":
            for chunk in split_message(msg.content, TELEGRAM_MAX_MESSAGE_LEN):
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
                    logger.warning("HTML parse failed, falling back to plain text: {}", e)
                    try:
                        await self._app.bot.send_message(
                            chat_id=chat_id,
                            text=chunk,
                            reply_parameters=reply_params,
                            **thread_kwargs,
                        )
                    except Exception as e2:
                        logger.error("Error sending Telegram message: {}", e2)

    async def _on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        if not update.message or not update.effective_user:
            return

        user = update.effective_user
        await update.message.reply_text(
            f"👋 Hi {user.first_name}! I'm nanobot.\n\n"
            "Send me a message and I'll respond!\n"
            "Type /help to see available commands."
        )

    async def _on_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command, bypassing ACL so all users can access it."""
        if not update.message:
            return
        await update.message.reply_text(
            "🐈 nanobot commands:\n"
            "/new — Start a new conversation\n"
            "/stop — Stop the current task\n"
            "/model — Show or switch the LLM model\n"
            "/tts — Control TTS settings (on/off, voice, provider)\n"
            "/trace — Toggle agent trace output (on/off/status)\n"
            "/stats — Show token usage statistics\n"
            "/help — Show available commands"
        )

    async def _on_tts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tts command for controlling TTS settings."""
        if not update.message or not update.effective_user:
            return

        chat_id = str(update.effective_message.chat_id)
        user_id = str(update.effective_user.id)
        
        # Check if user is allowed
        if not self.is_allowed(self._sender_id(update.effective_user)):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return

        # Parse command arguments
        args = context.args if context.args else []
        
        def _tts_status_msg(chat_id: str, extra: str = "") -> str:
            override = self._chat_tts_overrides.get(chat_id, {})
            enabled = override.get("enabled", self.tts_manager.config.enabled)
            provider = override.get("provider", self.tts_manager.config.provider)
            voice = override.get("voice", self.tts_manager.config.voice)
            return (
                f"🔊 TTS Settings:\n"
                f"Enabled: {'✅' if enabled else '❌'}\n"
                f"Provider: {provider}\n"
                f"Voice: {voice}"
                + (f"\n\n{extra}" if extra else "")
            )

        if not args:
            await update.message.reply_text(_tts_status_msg(
                chat_id,
                "Usage:\n"
                "/tts on — Enable TTS\n"
                "/tts off — Disable TTS\n"
                "/tts voices [locale] — List available voices\n"
                "/tts voice [name] — Change voice\n"
                "/tts provider [edge/openai/riva] — Change provider\n"
                "/tts status — Show current settings"
            ))
            return

        command = args[0].lower()
        
        if command == "on":
            # Enable TTS for this chat
            if chat_id not in self._chat_tts_overrides:
                self._chat_tts_overrides[chat_id] = {}
            self._chat_tts_overrides[chat_id]["enabled"] = True
            await update.message.reply_text("🔊 TTS enabled for this chat.")
            
        elif command == "off":
            # Disable TTS for this chat
            if chat_id not in self._chat_tts_overrides:
                self._chat_tts_overrides[chat_id] = {}
            self._chat_tts_overrides[chat_id]["enabled"] = False
            await update.message.reply_text("🔇 TTS disabled for this chat.")
            
        elif command == "status":
            await update.message.reply_text(_tts_status_msg(chat_id))
            
        elif command == "voices":
            # List available voices for current provider, with optional locale filter
            # Usage: /tts voices [locale_filter]  e.g. /tts voices en-US
            override = self._chat_tts_overrides.get(chat_id, {})
            provider_name = override.get("provider", self.tts_manager.config.provider)
            current_voice = override.get("voice", self.tts_manager.config.voice)
            locale_filter = args[1].lower() if len(args) > 1 else None

            await update.message.reply_text(f"⏳ Fetching voices for {provider_name}...")

            try:
                result = await self.tts_manager.get_supported_voices(provider_name)
                voices = result.get("voices", [])

                if not voices:
                    await update.message.reply_text("❌ No voices available or provider unreachable.")
                    return

                if provider_name == "edge":
                    # Edge has hundreds of voices — filter by locale
                    if locale_filter:
                        voices = [v for v in voices if locale_filter in v.get("locale", "").lower()]
                    else:
                        # Default: match locale of current voice (e.g. "en-US" from "en-US-AriaNeural")
                        parts = current_voice.split("-")
                        default_locale = f"{parts[0]}-{parts[1]}".lower() if len(parts) >= 2 else "en-us"
                        voices = [v for v in voices if default_locale in v.get("locale", "").lower()]

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
                        lines.append(f"… and {len(voices) - 20} more. Narrow with /tts voices en-US")
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
                            base_name = name_parts[0] if len(name_parts) > 1 and name_parts[1] in ["Neutral", "Calm", "Angry", "Happy", "Sad", "Fearful", "Disgust", "PleasantSurprised", "Disgusted"] else name

                            if base_name not in base_voices:
                                base_voices[base_name] = []
                            base_voices[base_name].append(v)

                        # Show base voices with available emotions
                        lines = [f"🎙️ Riva Magpie Voices"]
                        lines.append(f"💡 Filter: /tts voices en-us")
                        lines.append(f"💡 Set voice: /tts voice Magpie-Multilingual.EN-US.Mia.Happy\n")

                        for base_name in sorted(base_voices.keys())[:15]:
                            variants = base_voices[base_name]
                            marker = " ✅" if any(v["name"] == current_voice for v in variants) else ""
                            gender = variants[0].get("gender", "")
                            icon = "👩" if "Female" in gender else "👨" if "Male" in gender else "🎤"

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
                            icon = "👩" if "Female" in gender else "👨" if "Male" in gender else "🎤"
                            # Shorten name for display
                            display_name = v['name'].replace("Magpie-Multilingual.", "")
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
            if chat_id not in self._chat_tts_overrides:
                self._chat_tts_overrides[chat_id] = {}
            self._chat_tts_overrides[chat_id]["voice"] = new_voice
            await update.message.reply_text(f"🎙️ Voice changed to: {new_voice}")
            
        elif command == "provider" and len(args) > 1:
            # Change provider
            new_provider = args[1].lower()
            if new_provider in ["edge", "openai", "riva"]:
                if chat_id not in self._chat_tts_overrides:
                    self._chat_tts_overrides[chat_id] = {}
                self._chat_tts_overrides[chat_id]["provider"] = new_provider
                await update.message.reply_text(f"🔄 TTS provider changed to: {new_provider}")
            else:
                await update.message.reply_text("❌ Invalid provider. Use 'edge', 'openai', or 'riva'.")
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
            await update.message.reply_text(f"🔍 Trace mode: {status}\n\nUsage:\n/trace on — Show intermediate thoughts\n/trace off — Hide intermediate thoughts\n/trace status — Show current status")
            return

        command = args[0].lower()
        
        if command == "on":
            self._trace_enabled[chat_id_str] = True
            await update.message.reply_text("🔍 Trace mode **enabled** for this chat.\nIntermediate thoughts will now appear prefixed with 🤖")
        elif command == "off":
            self._trace_enabled[chat_id_str] = False
            await update.message.reply_text("🔍 Trace mode **disabled** for this chat.\nIntermediate thoughts will be hidden (only shown in logs).")
        elif command == "status":
            status = "on" if self._trace_enabled.get(chat_id_str, False) else "off"
            await update.message.reply_text(f"🔍 Trace mode is currently **{status}** for this chat.")
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
        if message.chat.type == "private" or message_thread_id is None:
            return None
        return f"telegram:{message.chat_id}:topic:{message_thread_id}"

    @staticmethod
    def _build_message_metadata(message, user) -> dict:
        """Build common Telegram inbound metadata payload."""
        return {
            "message_id": message.message_id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "is_group": message.chat.type != "private",
            "message_thread_id": getattr(message, "message_thread_id", None),
            "is_forum": bool(getattr(message.chat, "is_forum", False)),
        }

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

    async def _forward_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Forward slash commands (private chats only) to the bus for handling in AgentLoop."""
        if not update.message or not update.effective_user:
            return
        message = update.message
        user = update.effective_user
        self._remember_thread_context(message)
        await self._handle_message(
            sender_id=self._sender_id(user),
            chat_id=str(message.chat_id),
            content=message.text,
            metadata=self._build_message_metadata(message, user),
            session_key=self._derive_topic_session_key(message),
        )

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages (text, photos, voice, documents)."""
        if not update.message or not update.effective_user:
            return

        message = update.message
        user = update.effective_user
        chat_id = message.chat_id
        sender_id = self._sender_id(user)
        is_group = message.chat.type != "private"

        self._remember_thread_context(message)

        # Check group_policy for group chats
        if not await self._is_group_message_for_bot(message):
            logger.debug("Ignoring group message - bot not mentioned (group_policy=mention)")
            return

        # Capture topic thread_id for topic-aware routing
        thread_id = getattr(message, "message_thread_id", None)

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

        # Handle media files
        media_file = None
        media_type = None

        if message.photo:
            media_file = message.photo[-1]  # Largest photo
            media_type = "image"
        elif message.voice:
            media_file = message.voice
            media_type = "voice"
        elif message.audio:
            media_file = message.audio
            media_type = "audio"
        elif message.document:
            media_file = message.document
            media_type = "file"

        # Download media if present
        if media_file and self._app:
            try:
                file = await self._app.bot.get_file(media_file.file_id)
                ext = self._get_extension(media_type, getattr(media_file, 'mime_type', None))

                # Save to workspace/media/ (inside workspace when restrict_to_workspace is enabled)
                from pathlib import Path
                if self._workspace_path:
                    media_dir = Path(self._workspace_path) / "media"
                else:
                    media_dir = Path.home() / ".nanobot" / "media"
                media_dir.mkdir(parents=True, exist_ok=True)

                file_path = media_dir / f"{media_file.file_id[:16]}{ext}"
                file_path_str = str(file_path)
                await file.download_to_drive(file_path_str)

                media_paths.append(file_path_str)

                # Handle voice transcription
                if media_type == "voice" or media_type == "audio":
                    from nanobot.providers.transcription import GroqTranscriptionProvider
                    transcriber = GroqTranscriptionProvider(api_key=self.groq_api_key)
                    transcription = await transcriber.transcribe(file_path)
                    if transcription:
                        logger.info("Transcribed {}: {}...", media_type, transcription[:50])
                        content_parts.append(f"[transcription: {transcription}]")
                    else:
                        content_parts.append(f"[{media_type}: {file_path_str}]")
                else:
                    content_parts.append(f"[{media_type}: {file_path_str}]")

                logger.debug("Downloaded {} to {}", media_type, file_path)
            except Exception as e:
                logger.error("Failed to download media: {}", e)
                content_parts.append(f"[{media_type}: download failed]")

        content = "\n".join(content_parts) if content_parts else "[empty message]"

        logger.debug("Telegram message from {}: {}...", sender_id, content[:50])

        str_chat_id = str(chat_id)
        comp_key = self._composite_key(str_chat_id, thread_id)

        # Build metadata including thread_id for topic support
        msg_metadata = self._build_message_metadata(message, user)

        # Telegram media groups: buffer briefly, forward as one aggregated turn.
        if media_group_id := getattr(message, "media_group_id", None):
            key = f"{str_chat_id}:{media_group_id}"
            if key not in self._media_group_buffers:
                self._media_group_buffers[key] = {
                    "sender_id": sender_id, "chat_id": str_chat_id,
                    "contents": [], "media": [],
                    "metadata": msg_metadata,
                }
                self._start_typing(comp_key, thread_id)
            buf = self._media_group_buffers[key]
            if content and content != "[empty message]":
                buf["contents"].append(content)
            buf["media"].extend(media_paths)
            if key not in self._media_group_tasks:
                self._media_group_tasks[key] = asyncio.create_task(self._flush_media_group(key))
            return

        # Start typing indicator before processing
        self._start_typing(comp_key, thread_id)

        # Scope session per topic to isolate conversation context
        session_key = self._derive_topic_session_key(message)

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
            await self._handle_message(
                sender_id=buf["sender_id"], chat_id=buf["chat_id"],
                content=content, media=list(dict.fromkeys(buf["media"])),
                metadata=buf["metadata"],
            )
        finally:
            self._media_group_tasks.pop(key, None)

    async def _add_ack_reaction(self, chat_id: int, message_id: int) -> None:
        """Add a random emoji reaction to acknowledge message receipt (non-blocking)."""
        if not self._app:
            return

        try:
            emoji = _random_ack_reaction()
            if HAS_REACTION_TYPE:
                await self._app.bot.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[ReactionTypeEmoji(emoji)],
                    is_big=False
                )
            else:
                # Fallback for older versions
                await self._app.bot.set_message_reaction(
                    chat_id=chat_id,
                    message_id=message_id,
                    reaction=[{"type": "emoji", "emoji": emoji}],
                    is_big=False
                )
            logger.debug("Added ACK reaction {} to message {}", emoji, message_id)
        except Exception as e:
            # Reactions might not be supported in all chats, so just log at debug level
            logger.debug("Failed to add ACK reaction to message {}: {}", message_id, e)

    async def _send_thinking_message(
        self, chat_id: int, is_group: bool, thread_id: int | None = None,
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
        self._typing_tasks[comp_key] = asyncio.create_task(
            self._typing_loop(comp_key, thread_id)
        )

    def _stop_typing(self, comp_key: str) -> None:
        """Stop the typing indicator for a chat/topic."""
        task = self._typing_tasks.pop(comp_key, None)
        if task and not task.done():
            task.cancel()

    async def _typing_loop(self, comp_key: str, thread_id: int | None = None) -> None:
        """Repeatedly send 'typing' action until cancelled."""
        # Extract the numeric chat_id from the composite key
        raw_chat_id = comp_key.split(":", 1)[0]
        try:
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

    async def _on_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command to show token usage statistics."""
        if not update.message or not update.effective_user:
            return

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
            workspace_path = Path(self._workspace_path) if self._workspace_path else Path("~/.nanobot/workspace").expanduser()
            stats_manager = StatsManager(workspace_path)

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
        logger.error("Telegram error: {}", context.error)

    def _get_extension(
        self,
        media_type: str,
        mime_type: str | None,
        filename: str | None = None,
    ) -> str:
        """Get file extension based on media type and optional filename."""
        if mime_type:
            ext_map = {
                "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
                "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a",
            }
            if mime_type in ext_map:
                return ext_map[mime_type]

        if filename:
            from pathlib import Path
            p = Path(filename)
            if p.suffixes:
                # Return full compound extension if present (e.g. .tar.gz)
                return ''.join(p.suffixes).lower()
            if p.suffix:
                return p.suffix.lower()

        type_map = {"image": ".jpg", "voice": ".ogg", "audio": ".mp3", "file": ""}
        return type_map.get(media_type, "")
