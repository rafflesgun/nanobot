"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
import os
import time
from contextlib import AsyncExitStack, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.agent.memory import MemoryConsolidator
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.skills import BUILTIN_SKILLS_DIR
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.command import CommandContext, CommandRouter, register_builtin_commands
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.session.manager import Session, SessionManager
from nanobot.utils.stats import StatsManager

if TYPE_CHECKING:
    from nanobot.config.schema import ChannelsConfig, ExecToolConfig, WebSearchConfig
    from nanobot.cron.service import CronService


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    _TOOL_RESULT_MAX_CHARS = 16_000

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        context_window_tokens: int = 65_536,
        web_search_config: WebSearchConfig | None = None,
        web_proxy: str | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        extra_read: list[str] | None = None,
        extra_write: list[str] | None = None,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        fallback_model: str | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig, WebSearchConfig

        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.context_window_tokens = context_window_tokens
        self.web_search_config = web_search_config or WebSearchConfig()
        self.web_proxy = web_proxy
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.extra_read = extra_read or []
        self.extra_write = extra_write or []
        self.fallback_model = fallback_model
        self._start_time = time.time()
        self._last_usage: dict[str, int] = {}

        self.context = ContextBuilder(workspace)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.stats_manager = StatsManager(workspace)
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            fallback_model=self.fallback_model,
            web_search_config=self.web_search_config,
            web_proxy=web_proxy,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            extra_read=self.extra_read,
            extra_write=self.extra_write,
        )

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._model_overrides: dict[str, str] = {}  # session_key -> model override
        self._background_tasks: list[asyncio.Task] = []
        self._session_locks: dict[str, asyncio.Lock] = {}
        # NANOBOT_MAX_CONCURRENT_REQUESTS: <=0 means unlimited; default 3.
        _max = int(os.environ.get("NANOBOT_MAX_CONCURRENT_REQUESTS", "3"))
        self._concurrency_gate: asyncio.Semaphore | None = (
            asyncio.Semaphore(_max) if _max > 0 else None
        )
        self.memory_consolidator = MemoryConsolidator(
            workspace=workspace,
            provider=provider,
            model=self.model,
            sessions=self.sessions,
            context_window_tokens=context_window_tokens,
            build_messages=self.context.build_messages,
            get_tool_definitions=self.tools.get_definitions,
            max_completion_tokens=getattr(getattr(provider, "generation", None), "max_tokens", 4096),
        )
        self._register_default_tools()
        self.commands = CommandRouter()
        register_builtin_commands(self.commands)

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir: list[Path] = ([self.workspace] + ([Path(p) for p in self.extra_write] if self.extra_write else [])) if self.restrict_to_workspace else None
        extra_read: list[Path] = ([BUILTIN_SKILLS_DIR] + ([Path(p) for p in self.extra_read] if self.extra_read else [])) if allowed_dir else None
        self.tools.register(ReadFileTool(workspace=self.workspace, allowed_dir=allowed_dir, extra_allowed_dirs=extra_read))
        for cls in (WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        if self.exec_config.enable:
            self.tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
                allowed_dirs=allowed_dir,
                path_append=self.exec_config.path_append,
            ))
        self.tools.register(WebSearchTool(config=self.web_search_config, proxy=self.web_proxy))
        self.tools.register(WebFetchTool(proxy=self.web_proxy))
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanobot.agent.tools.mcp import connect_mcp_servers
        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except BaseException as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    def _set_tool_context(
        self,
        channel: str,
        chat_id: str,
        message_id: str | None = None,
        thread_id: int | None = None,
    ) -> None:
        """Update context for all tools that need routing info."""
        for name in ("message", "spawn", "cron"):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    if name == "message":
                        tool.set_context(channel, chat_id, message_id, thread_id)
                    elif name == "cron":
                        tool.set_context(channel, chat_id, thread_id)
                    else:
                        tool.set_context(channel, chat_id)

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        from nanobot.utils.helpers import strip_think
        return strip_think(text) or None

    @staticmethod
    def _fix_missing_newlines(text: str | None) -> str | None:
        """Heuristically insert missing newlines.

        Some models (e.g. minimax-m2.5) occasionally return structured content
        with no newline characters — bullet lists, numbered items, and bold
        headings all run together on a single line.  This method detects
        common patterns and inserts ``\\n`` where they were clearly intended.

        The method is intentionally conservative: it only acts when the text
        already contains very few newlines relative to its length, so
        well-formatted responses pass through unchanged.
        """
        if not text:
            return text

        # If the text already has a reasonable newline density, leave it alone.
        # Heuristic: at least 1 newline per 300 chars means it's fine.
        if text.count("\n") >= max(1, len(text) // 300):
            return text

        # ── Bullet / list item runs ────────────────────────────────────
        # "some text - item" → "some text\n- item"  (but not "well-known")
        # Only match " - " preceded by a sentence-end or at least 2 words.
        text = re.sub(r"(?<=[.!?:;])\s+(?=- )", "\n", text)
        # Catch "text - Capitalised item" which is very likely a list.
        text = re.sub(r" (?=- [A-Z\u0400-\u04FF\u4e00-\u9fff])", "\n", text)

        # ── Numbered items ─────────────────────────────────────────────
        # "text 1. First" → "text\n1. First"  /  "text 1) First" → …
        text = re.sub(r"(?<=[.!?:;])\s+(?=\d{1,3}[.)]\s)", "\n", text)

        # ── Bold-header patterns (**Header**: …) ──────────────────────
        text = re.sub(r"(?<=[.!?])\s+(?=\*\*)", "\n", text)

        # ── Markdown headers (# Title) ────────────────────────────────
        text = re.sub(r"(?<=[.!?])\s+(?=#{1,6}\s)", "\n", text)

        return text

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            args = (tc.arguments[0] if isinstance(tc.arguments, list) else tc.arguments) or {}
            val = next(iter(args.values()), None) if isinstance(args, dict) else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
        model_override: str | None = None,
        on_turn_saved: Callable[[list[dict]], Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
        *,
        channel: str = "cli",
        chat_id: str = "direct",
        message_id: str | None = None,
    ) -> tuple[str | None, list[str], list[dict]]:
        """Run the agent iteration loop.

        Args:
            initial_messages: Starting messages for the conversation
            on_progress: Callback for progress updates during processing
            model_override: Specific model to use for this loop
            on_turn_saved: Callback triggered after each turn is saved incrementally
            on_stream: called with each content delta during streaming.
            on_stream_end(resuming): called when a streaming session finishes.
        """
        messages = initial_messages
        iteration = 0
        final_content = None
        tools_used: list[str] = []
        effective_model = model_override or self.model

        # Wrap on_stream with stateful think-tag filter so downstream
        # consumers (CLI, channels) never see <think> blocks.
        _raw_stream = on_stream
        _stream_buf = ""

        async def _filtered_stream(delta: str) -> None:
            nonlocal _stream_buf
            from nanobot.utils.helpers import strip_think
            prev_clean = strip_think(_stream_buf)
            _stream_buf += delta
            new_clean = strip_think(_stream_buf)
            incremental = new_clean[len(prev_clean):]
            if incremental and _raw_stream:
                await _raw_stream(incremental)

        def _on_retry(attempt: int, total: int) -> None:
            if on_progress:
                asyncio.create_task(on_progress(f"Retrying... (attempt {attempt}/{total})"))

        while iteration < self.max_iterations:
            iteration += 1

            tool_defs = self.tools.get_definitions()

            try:
                if on_stream:
                    response = await self.provider.chat_stream_with_retry(
                        messages=messages,
                        tools=tool_defs,
                        model=effective_model,
                        on_content_delta=_filtered_stream,
                        on_retry=_on_retry,
                    )
                else:
                    response = await self.provider.chat_with_retry(
                        messages=messages,
                        tools=tool_defs,
                        model=effective_model,
                        on_retry=_on_retry,
                    )
            except Exception as e:
                # Check if there's a fallback model and this is a provider error
                error_msg = str(e).lower()
                if (self.fallback_model and
                    ('provider returned error' in error_msg or
                     '502' in error_msg or
                     '503' in error_msg or
                     'timeout' in error_msg or
                     '404' in error_msg or
                     '403' in error_msg or
                     'not found' in error_msg or
                     'invalid model' in error_msg or
                     'allocationquota' in error_msg or
                     'free tier' in error_msg or
                     'exhausted' in error_msg)):
                    logger.warning("Primary model failed, trying fallback model: {}", self.fallback_model)
                    try:
                        if on_stream:
                            response = await self.provider.chat_stream_with_retry(
                                messages=messages,
                                tools=tool_defs,
                                model=self.fallback_model,
                                on_content_delta=_filtered_stream,
                                on_retry=_on_retry,
                            )
                        else:
                            response = await self.provider.chat_with_retry(
                                messages=messages,
                                tools=tool_defs,
                                model=self.fallback_model,
                                on_retry=_on_retry,
                            )
                    except Exception as fallback_error:
                        logger.error("Both primary and fallback models failed: {}", fallback_error)
                        raise e  # Re-raise the original error if fallback also fails
                else:
                    raise e  # Re-raise the original error if no fallback or different error type

            usage = response.usage or {}
            self._last_usage = {
                "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
            }

            if response.has_tool_calls:
                if on_stream and on_stream_end:
                    await on_stream_end(resuming=True)
                    _stream_buf = ""

                if on_progress:
                    if not on_stream:
                        thought = self._strip_think(response.content)
                        thought = self._fix_missing_newlines(thought)
                        if thought:
                            await on_progress(thought)
                    tool_hint = self._tool_hint(response.tool_calls)
                    tool_hint = self._strip_think(tool_hint)
                    await on_progress(tool_hint, tool_hint=True)

                tool_call_dicts = [
                    tc.to_openai_tool_call()
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )

                for tc in response.tool_calls:
                    tools_used.append(tc.name)
                    args_str = json.dumps(tc.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tc.name, args_str[:200])

                # Re-bind tool context right before execution so that
                # concurrent sessions don't clobber each other's routing.
                self._set_tool_context(channel, chat_id, message_id)

                # Execute all tool calls concurrently — the LLM batches
                # independent calls in a single response on purpose.
                # return_exceptions=True ensures all results are collected
                # even if one tool is cancelled or raises BaseException.
                results = await asyncio.gather(*(
                    self.tools.execute(tc.name, tc.arguments)
                    for tc in response.tool_calls
                ), return_exceptions=True)

                for tool_call, result in zip(response.tool_calls, results):
                    if isinstance(result, BaseException):
                        result = f"Error: {type(result).__name__}: {result}"
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )

                # Incremental save after processing tool calls
                if on_turn_saved:
                    await on_turn_saved(messages)
            else:
                if on_stream and on_stream_end:
                    await on_stream_end(resuming=False)
                    _stream_buf = ""

                clean = self._strip_think(response.content)
                clean = self._fix_missing_newlines(clean)
                if response.finish_reason == "error":
                    logger.error("LLM returned error: {}", (clean or "")[:200])
                    final_content = clean or "Sorry, I encountered an error calling the AI model."
                    break
                messages = self.context.add_assistant_message(
                    messages, clean, reasoning_content=response.reasoning_content,
                    thinking_blocks=response.thinking_blocks,
                )
                final_content = clean
                break

        if final_content is None and iteration >= self.max_iterations:
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            final_content = (
                f"I reached the maximum number of tool call iterations ({self.max_iterations}) "
                "without completing the task. You can try breaking the task into smaller steps."
            )

        return final_content, tools_used, messages

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                # Preserve real task cancellation so shutdown can complete cleanly.
                # Only ignore non-task CancelledError signals that may leak from integrations.
                if not self._running or asyncio.current_task().cancelling():
                    raise
                continue
            except Exception as e:
                logger.warning("Error consuming inbound message: {}, continuing...", e)
                continue

            raw = msg.content.strip()
            if self.commands.is_priority(raw):
                ctx = CommandContext(msg=msg, session=None, key=msg.session_key, raw=raw, loop=self)
                result = await self.commands.dispatch_priority(ctx)
                if result:
                    await self.bus.publish_outbound(result)
                continue
            task = asyncio.create_task(self._dispatch(msg))
            self._active_tasks.setdefault(msg.session_key, []).append(task)
            task.add_done_callback(lambda t, k=msg.session_key: self._active_tasks.get(k, []) and self._active_tasks[k].remove(t) if t in self._active_tasks.get(k, []) else None)

    @staticmethod
    def _extract_cmd(content: str) -> str:
        """Return the leading slash-command from content, stripping any @mention prefix.

        Handles group formats like "@BotName /stop" as well as plain "/stop".
        Returns an empty string if no slash command is found.
        """
        text = content.strip()
        if text.startswith("@"):
            text = re.sub(r'^@\S+\s*', '', text)
        text = text.strip().lower()
        # Return only the command token (first word), without any @suffix or args
        token = text.split()[0] if text else ""
        return token.split("@")[0] if token.startswith("/") else ""

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message: per-session serial, cross-session concurrent."""
        lock = self._session_locks.setdefault(msg.session_key, asyncio.Lock())
        gate = self._concurrency_gate or nullcontext()
        async with lock, gate:
            try:
                on_stream = on_stream_end = None
                if msg.metadata.get("_wants_stream"):
                    async def on_stream(delta: str) -> None:
                        meta = {
                            "_stream_delta": True,
                            "message_thread_id": msg.metadata.get("message_thread_id"),
                            "message_id": msg.metadata.get("message_id"),
                        }
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel, chat_id=msg.chat_id,
                            content=delta, metadata=meta,
                        ))

                    async def on_stream_end(*, resuming: bool = False) -> None:
                        meta = {
                            "_stream_end": True,
                            "_resuming": resuming,
                            "message_thread_id": msg.metadata.get("message_thread_id"),
                            "message_id": msg.metadata.get("message_id"),
                        }
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel, chat_id=msg.chat_id,
                            content="", metadata=meta,
                        ))

                response = await self._process_message(
                    msg, on_stream=on_stream, on_stream_end=on_stream_end,
                )
                if response is not None:
                    await self.bus.publish_outbound(response)
                elif msg.channel == "cli":
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="", metadata=msg.metadata or {},
                    ))
            except asyncio.CancelledError:
                logger.info("Task cancelled for session {}", msg.session_key)
                raise
            except Exception:
                logger.exception("Error processing message for session {}", msg.session_key)
                await self.bus.publish_outbound(OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content="Sorry, I encountered an error.",
                ))

    async def close_mcp(self) -> None:
        """Drain pending background archives, then close MCP connections."""
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None

    def _schedule_background(self, coro) -> None:
        """Schedule a coroutine as a tracked background task (drained on shutdown)."""
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        task.add_done_callback(self._background_tasks.remove)

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        # System messages: parse origin from chat_id ("channel:chat_id")
        if msg.channel == "system":
            channel, chat_id = (msg.chat_id.split(":", 1) if ":" in msg.chat_id
                                else ("cli", msg.chat_id))
            logger.info("Processing system message from {}", msg.sender_id)
            key = f"{channel}:{chat_id}"
            session = self.sessions.get_or_create(key)
            await self.memory_consolidator.maybe_consolidate_by_tokens(session)
            self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"))
            history = session.get_history(max_messages=0)
            current_role = "assistant" if msg.sender_id == "subagent" else "user"
            messages = self.context.build_messages(
                history=history,
                current_message=msg.content, channel=channel, chat_id=chat_id,
                current_role=current_role,
            )
            final_content, _, all_msgs = await self._run_agent_loop(
                messages, channel=channel, chat_id=chat_id,
                message_id=msg.metadata.get("message_id"),
            )
            self._save_turn(session, all_msgs, 1 + len(history))
            self.sessions.save(session)
            self._schedule_background(self.memory_consolidator.maybe_consolidate_by_tokens(session))
            return OutboundMessage(channel=channel, chat_id=chat_id,
                                  content=final_content or "Background task completed.")

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        # Slash commands
        # Strip a leading @mention (e.g. "@BotName /model gpt-4" -> "/model gpt-4")
        raw = msg.content.strip()
        if raw.startswith("@"):
            raw = re.sub(r'^@\S+\s*', '', raw).strip()
        ctx = CommandContext(msg=msg, session=session, key=key, raw=raw, loop=self)
        if result := await self.commands.dispatch(ctx):
            return result

        await self.memory_consolidator.maybe_consolidate_by_tokens(session)

        self._set_tool_context(
            msg.channel, msg.chat_id,
            msg.metadata.get("message_id"),
            msg.metadata.get("message_thread_id"),
        )
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        history = session.get_history(max_messages=0)
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel, chat_id=msg.chat_id,
        )

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        # Define the incremental save callback
        async def _on_turn_saved(messages: list[dict]) -> None:
            self._save_turn(session, messages, 1 + len(history))
            self.sessions.save(session)
            # Record token usage if provider supports it
            if hasattr(self.provider, 'get_usage'):
                usage = self.provider.get_usage()
                if usage:
                    self.stats_manager.record_usage(
                        msg.channel,
                        msg.chat_id,
                        self.model,
                        usage.get('input_tokens', 0),
                        usage.get('output_tokens', 0),
                        usage.get('total_tokens', 0),
                        session.key
                    )

        final_content, _, all_msgs = await self._run_agent_loop(
            initial_messages,
            on_progress=on_progress or _bus_progress,
            model_override=self._model_overrides.get(key),
            on_turn_saved=_on_turn_saved,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
            channel=msg.channel, chat_id=msg.chat_id,
            message_id=msg.metadata.get("message_id"),
        )

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        self._save_turn(session, all_msgs, 1 + len(history))
        self.sessions.save(session)
        self._schedule_background(self.memory_consolidator.maybe_consolidate_by_tokens(session))

        if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
            return None

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)

        # Add token usage hint if configured
        if (self.channels_config and self.channels_config.show_usage and
            hasattr(self.provider, 'get_usage')):
            usage = self.provider.get_usage()
            if usage:
                usage_hint = f"\n\n💡 Token usage: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out / {usage.get('total_tokens', 0)} total"
                final_content += usage_hint

        meta = dict(msg.metadata or {})
        if on_stream is not None:
            meta["_streamed"] = True
        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id, content=final_content,
            metadata=meta,
        )

    def _handle_model_command(self, msg: InboundMessage, session_key: str, raw_content: str | None = None) -> OutboundMessage:
        """Handle /model command — show current model or switch to a new one."""
        # Use pre-stripped content (leading @mention already removed) if provided
        raw = (raw_content or msg.content).strip()
        # Strip @bot_username suffix (e.g. /model@mybot)
        parts = raw.split(None, 1)
        model_arg = parts[1].strip() if len(parts) > 1 else ""
        _meta = msg.metadata or {}

        if not model_arg:
            # Show current model
            effective = self._model_overrides.get(session_key, self.model)
            is_override = session_key in self._model_overrides
            status = (
                f"🤖 Current model: `{effective}`"
                + ("\n_(session override — use `/model reset` to revert to default)_" if is_override else "")
                + f"\n\nSwitch model with `/model <model-id>`."
            )
            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=status,
                metadata=_meta,
            )

        # /model reset — revert to default
        if model_arg.lower() == "reset":
            removed = self._model_overrides.pop(session_key, None)
            if removed:
                return OutboundMessage(
                    channel=msg.channel, chat_id=msg.chat_id,
                    content=f"🔄 Model reset to default: `{self.model}`",
                    metadata=_meta,
                )
            return OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id,
                content=f"Already using the default model: `{self.model}`",
                metadata=_meta,
            )

        # /model <model-id> — switch model
        new_model = model_arg.strip("`")
        self._model_overrides[session_key] = new_model
        logger.info("Model switched to '{}' for session {}", new_model, session_key)
        return OutboundMessage(
            channel=msg.channel, chat_id=msg.chat_id,
            content=f"✅ Model switched to `{new_model}` for this session.\nUse `/model reset` to revert to default.",
            metadata=_meta,
        )

    async def _handle_stats_command(self, msg: InboundMessage, args: list[str]) -> OutboundMessage:
        """Handle /stats command — show token usage statistics."""
        _meta = msg.metadata or {}

        # Check if this is a topic request but not in a topic
        if args and args[0].lower() == "topic" and not _meta.get("message_thread_id"):
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="❌ This command is only available in topic threads.",
                metadata=_meta,
            )

        # Get stats based on scope
        if args and args[0].lower() == "all":
            # Total stats across all channels
            stats = self.stats_manager.get_total_stats()
            if not stats:
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="📊 No token usage statistics found.",
                    metadata=_meta,
                )

            total_messages = sum(stats.values())
            total_tokens = sum(stat["total_tokens"] for stat in stats.values())

            response = f"📊 Total Token Usage Statistics\n\n"
            response += f"• Total messages: {total_messages}\n"
            response += f"• Total tokens: {total_tokens:,}\n\n"

            for channel, stat in stats.items():
                response += f"📡 {channel}: {stat['total_tokens']:,} tokens ({stat['count']} messages)\n"

            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=response,
                metadata=_meta,
            )

        # Get stats for current chat/topic
        stats = self.stats_manager.get_stats(msg.channel, msg.chat_id)
        if not stats:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="📊 No token usage statistics found for this chat.",
                metadata=_meta,
            )

        total_messages = stats["count"]
        total_input = stats["total_input_tokens"]
        total_output = stats["total_output_tokens"]
        total_tokens = stats["total_tokens"]

        response = f"📊 Token Usage Statistics"
        if _meta.get("message_thread_id"):
            response += f" (Topic {_meta.get('message_thread_id')})"
        else:
            response += " (This Chat)"
        response += "\n\n"

        response += f"• Total messages: {total_messages}\n"
        response += f"• Input tokens: {total_input:,}\n"
        response += f"• Output tokens: {total_output:,}\n"
        response += f"• Total tokens: {total_tokens:,}\n\n"

        # Add model breakdown if available
        model_stats = {}

        if model_stats:
            response += "🤖 Model breakdown:\n"
            for model, tokens in sorted(model_stats.items(), key=lambda x: x[1], reverse=True):
                response += f"• {model}: {tokens:,} tokens\n"

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=response,
            metadata=_meta,
        )

    async def _handle_tts_command(self, msg: InboundMessage, args: list[str]) -> OutboundMessage:
        """Handle /tts command — toggle text-to-speech."""
        _meta = msg.metadata or {}

        # Placeholder implementation - this should interact with TTS configuration
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content="🔊 TTS functionality is available.\n\nUse `/tts enable` to enable or `/tts disable` to disable.",
            metadata=_meta,
        )

    @staticmethod
    def _image_placeholder(block: dict[str, Any]) -> dict[str, str]:
        """Convert an inline image block into a compact text placeholder."""
        path = (block.get("_meta") or {}).get("path", "")
        return {"type": "text", "text": f"[image: {path}]" if path else "[image]"}

    def _sanitize_persisted_blocks(
        self,
        content: list[dict[str, Any]],
        *,
        truncate_text: bool = False,
        drop_runtime: bool = False,
    ) -> list[dict[str, Any]]:
        """Strip volatile multimodal payloads before writing session history."""
        filtered: list[dict[str, Any]] = []
        for block in content:
            if not isinstance(block, dict):
                filtered.append(block)
                continue

            if (
                drop_runtime
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
                and block["text"].startswith(ContextBuilder._RUNTIME_CONTEXT_TAG)
            ):
                continue

            if (
                block.get("type") == "image_url"
                and block.get("image_url", {}).get("url", "").startswith("data:image/")
            ):
                filtered.append(self._image_placeholder(block))
                continue

            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text = block["text"]
                if truncate_text and len(text) > self._TOOL_RESULT_MAX_CHARS:
                    text = text[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
                filtered.append({**block, "text": text})
                continue

            filtered.append(block)

        return filtered

    def _save_turn(self, session: Session, messages: list[dict], skip: int) -> None:
        """Save new-turn messages into session, truncating large tool results."""
        from datetime import datetime
        for m in messages[skip:]:
            entry = dict(m)
            role, content = entry.get("role"), entry.get("content")
            if role == "assistant" and not content and not entry.get("tool_calls"):
                continue  # skip empty assistant messages — they poison session context
            if role == "tool":
                if isinstance(content, str) and len(content) > self._TOOL_RESULT_MAX_CHARS:
                    entry["content"] = content[:self._TOOL_RESULT_MAX_CHARS] + "\n... (truncated)"
                elif isinstance(content, list):
                    filtered = self._sanitize_persisted_blocks(content, truncate_text=True)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            elif role == "user":
                if isinstance(content, str) and content.startswith(ContextBuilder._RUNTIME_CONTEXT_TAG):
                    # Strip the runtime-context prefix, keep only the user text.
                    parts = content.split("\n\n", 1)
                    if len(parts) > 1 and parts[1].strip():
                        entry["content"] = parts[1]
                    else:
                        continue
                if isinstance(content, list):
                    filtered = self._sanitize_persisted_blocks(content, drop_runtime=True)
                    if not filtered:
                        continue
                    had_non_text_blocks = any(
                        isinstance(c, dict) and c.get("type") != "text" for c in content
                    )
                    # If all remaining items are plain text blocks, flatten to a
                    # string so history never contains list-format user messages.
                    # List-content in history causes 400 errors on providers that
                    # expect content to be a dict/string, not a list.
                    if (
                        not had_non_text_blocks
                        and all(isinstance(c, dict) and c.get("type") == "text" for c in filtered)
                    ):
                        entry["content"] = "\n".join(c.get("text", "") for c in filtered)
                    else:
                        entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        thread_id: int | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
    ) -> OutboundMessage | None:
        """Process a message directly and return the outbound payload."""
        await self._connect_mcp()
        meta: dict = {}
        if thread_id:
            meta["message_thread_id"] = thread_id
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content, metadata=meta)
        return await self._process_message(
            msg, session_key=session_key, on_progress=on_progress,
            on_stream=on_stream, on_stream_end=on_stream_end,
        )
