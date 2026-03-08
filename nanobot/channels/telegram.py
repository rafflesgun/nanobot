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

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import TelegramConfig
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

        # Add message handler for text, photos, voice, documents.
        # In groups, commands typed as "@BotName /cmd" are plain TEXT (not COMMAND
        # entities from Telegram's perspective when prefixed by a mention), so we
        # include all TEXT here.  The ~filters.COMMAND exclusion only applies in
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

        # Only stop typing indicator for final responses
        if not msg.metadata.get("_progress", False):
            self._stop_typing(comp_key)

        try:
            chat_id = int(msg.chat_id)
        except ValueError:
            logger.error("Invalid chat_id: {}", msg.chat_id)
            return

        # Build optional kwargs for message_thread_id (topic support)
        thread_kwargs: dict = {}
        if thread_id:
            thread_kwargs["message_thread_id"] = thread_id

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

        # Send text content
        if msg.content and msg.content != "[empty message]":
            is_progress = msg.metadata.get("_progress", False)

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
            "/help — Show available commands"
        )

    @staticmethod
    def _sender_id(user) -> str:
        """Build sender_id with username for allowlist matching."""
        sid = str(user.id)
        return f"{sid}|{user.username}" if user.username else sid

    async def _forward_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Forward slash commands (private chats only) to the bus for handling in AgentLoop."""
        if not update.message or not update.effective_user:
            return
        metadata: dict = {}
        thread_id = getattr(update.message, "message_thread_id", None)
        if thread_id:
            metadata["message_thread_id"] = thread_id
        str_chat_id = str(update.message.chat_id)
        # Scope session per topic to isolate conversation context
        session_key = f"telegram:{str_chat_id}:{thread_id}" if thread_id else None
        await self._handle_message(
            sender_id=self._sender_id(update.effective_user),
            chat_id=str_chat_id,
            content=update.message.text,
            metadata=metadata,
            session_key=session_key,
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

        # Check group_policy for group chats
        if self.config.group_policy == "mention" and is_group:
            # Check if bot is mentioned in the message (support text and captions)
            bot_mentioned = False

            # Fetch bot info once
            bot_info = None
            if self._app:
                bot_info = await self._app.bot.get_me()

            # Helper to inspect entities against a source text
            def _check_entities(entities, source_text):
                nonlocal bot_mentioned, bot_info
                if not entities or not source_text:
                    return
                for entity in entities:
                    if getattr(entity, "type", None) == "mention":
                        try:
                            mention_text = source_text[entity.offset:entity.offset + entity.length]
                        except Exception:
                            continue
                        if bot_info and mention_text == f"@{bot_info.username}":
                            bot_mentioned = True
                            return
                    elif getattr(entity, "type", None) == "text_mention" and getattr(entity, "user", None):
                        if bot_info and entity.user.id == bot_info.id:
                            bot_mentioned = True
                            return

            # Check entities in message.text
            _check_entities(getattr(message, "entities", None), getattr(message, "text", None))

            # Also check entities in caption (for media messages where mention may be in caption)
            if not bot_mentioned:
                _check_entities(getattr(message, "caption_entities", None), getattr(message, "caption", None))

            # Check if message is a reply to bot's message
            if not bot_mentioned and message.reply_to_message and bot_info:
                if getattr(message.reply_to_message.from_user, "id", None) == bot_info.id:
                    bot_mentioned = True

            # If bot is not mentioned, ignore the message
            if not bot_mentioned:
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
            content_parts.append(message.text)
        if message.caption:
            content_parts.append(message.caption)

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
                await file.download_to_drive(str(file_path))

                media_paths.append(str(file_path))

                # Handle voice transcription
                if media_type == "voice" or media_type == "audio":
                    from nanobot.providers.transcription import GroqTranscriptionProvider
                    transcriber = GroqTranscriptionProvider(api_key=self.groq_api_key)
                    transcription = await transcriber.transcribe(file_path)
                    if transcription:
                        logger.info("Transcribed {}: {}...", media_type, transcription[:50])
                        content_parts.append(f"[transcription: {transcription}]")
                    else:
                        content_parts.append(f"[{media_type}: {file_path}]")
                else:
                    content_parts.append(f"[{media_type}: {file_path}]")

                logger.debug("Downloaded {} to {}", media_type, file_path)
            except Exception as e:
                logger.error("Failed to download media: {}", e)
                content_parts.append(f"[{media_type}: download failed]")

        content = "\n".join(content_parts) if content_parts else "[empty message]"

        logger.debug("Telegram message from {}: {}...", sender_id, content[:50])

        str_chat_id = str(chat_id)
        comp_key = self._composite_key(str_chat_id, thread_id)

        # Build metadata including thread_id for topic support
        msg_metadata: dict = {
            "message_id": message.message_id,
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "is_group": is_group,
        }
        if thread_id:
            msg_metadata["message_thread_id"] = thread_id

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
        session_key = f"telegram:{str_chat_id}:{thread_id}" if thread_id else None

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

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log polling / handler errors instead of silently swallowing them."""
        logger.error("Telegram error: {}", context.error)

    def _get_extension(self, media_type: str, mime_type: str | None) -> str:
        """Get file extension based on media type."""
        if mime_type:
            ext_map = {
                "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
                "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a",
            }
            if mime_type in ext_map:
                return ext_map[mime_type]

        type_map = {"image": ".jpg", "voice": ".ogg", "audio": ".mp3", "file": ""}
        return type_map.get(media_type, "")
