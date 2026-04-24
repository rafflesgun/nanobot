"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import re
import time
from contextlib import AsyncExitStack, nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from nanobot.agent.autocompact import AutoCompact
from nanobot.agent.context import ContextBuilder
from nanobot.agent.hook import AgentHook, AgentHookContext, CompositeHook
from nanobot.agent.memory import Consolidator, Dream
from nanobot.agent.runner import _MAX_INJECTIONS_PER_TURN, AgentRunSpec, AgentRunner
from nanobot.agent.runner import _PERSISTED_MODEL_ERROR_PLACEHOLDER
from nanobot.agent.skills import BUILTIN_SKILLS_DIR
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.search import GlobTool, GrepTool
from nanobot.agent.tools.session_search import SessionSearchTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.skill_manage import SkillManageTool
from nanobot.agent.tools.self import MyTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.agent.tools.workflow import WorkflowListTool, WorkflowRunTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.command import CommandContext, CommandRouter, register_builtin_commands
from nanobot.config.paths import (
    load_model_overrides,
    save_model_overrides,
    load_temperature_overrides,
    save_temperature_overrides,
)
from nanobot.bus.queue import MessageBus
from nanobot.command import CommandContext, CommandRouter, register_builtin_commands
from nanobot.config.schema import AgentDefaults
from nanobot.providers.base import LLMProvider
from nanobot.session.manager import Session, SessionManager
from nanobot.utils.helpers import image_placeholder_text, truncate_text as truncate_text_fn
from nanobot.utils.runtime import (
    EMPTY_FINAL_RESPONSE_MESSAGE,
    format_provider_error,
    is_provider_error_message,
)
from nanobot.utils.stats import StatsManager
from nanobot.utils.document import extract_documents
from nanobot.utils.helpers import image_placeholder_text
from nanobot.utils.helpers import truncate_text as truncate_text_fn
from nanobot.utils.runtime import EMPTY_FINAL_RESPONSE_MESSAGE

if TYPE_CHECKING:
    from nanobot.config.schema import ChannelsConfig, ExecToolConfig, ToolsConfig, WebToolsConfig
    from nanobot.cron.service import CronService


UNIFIED_SESSION_KEY = "unified:default"


class _LoopHook(AgentHook):
    """Core hook for the main loop."""

    def __init__(
        self,
        agent_loop: AgentLoop,
        on_progress: Callable[..., Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
        *,
        channel: str = "cli",
        chat_id: str = "direct",
        message_id: str | None = None,
        thread_id: int | None = None,
        session_key: str | None = None,
    ) -> None:
        super().__init__(reraise=True)
        self._loop = agent_loop
        self._on_progress = on_progress
        self._on_stream = on_stream
        self._on_stream_end = on_stream_end
        self._channel = channel
        self._chat_id = chat_id
        self._message_id = message_id
        self._thread_id = thread_id
        self._session_key = session_key
        self._stream_buf = ""

    def wants_streaming(self) -> bool:
        return self._on_stream is not None

    async def on_stream(self, context: AgentHookContext, delta: str) -> None:
        from nanobot.utils.helpers import strip_think

        prev_clean = strip_think(self._stream_buf)
        self._stream_buf += delta
        new_clean = strip_think(self._stream_buf)
        incremental = new_clean[len(prev_clean) :]
        if incremental and self._on_stream:
            await self._on_stream(incremental)

    async def on_stream_end(self, context: AgentHookContext, *, resuming: bool) -> None:
        if self._on_stream_end:
            await self._on_stream_end(resuming=resuming)
        self._stream_buf = ""

    async def before_iteration(self, context: AgentHookContext) -> None:
        self._loop._current_iteration = context.iteration

    async def before_execute_tools(self, context: AgentHookContext) -> None:
        if self._on_progress:
            if not self._on_stream:
                thought = self._loop._strip_think(
                    context.response.content if context.response else None
                )
                if thought:
                    await self._on_progress(thought)
            tool_hint = self._loop._strip_think(self._loop._tool_hint(context.tool_calls))
            await self._on_progress(tool_hint, tool_hint=True)
        for tc in context.tool_calls:
            args_str = json.dumps(tc.arguments, ensure_ascii=False)
            logger.info("Tool call: {}({})", tc.name, args_str[:200])
        self._loop._set_tool_context(
            self._channel, self._chat_id, self._message_id, self._thread_id
        )

    async def after_iteration(self, context: AgentHookContext) -> None:
        u = context.usage or {}
        logger.debug(
            "LLM usage: prompt={} completion={} cached={}",
            u.get("prompt_tokens", 0),
            u.get("completion_tokens", 0),
            u.get("cached_tokens", 0),
        )

    def finalize_content(self, context: AgentHookContext, content: str | None) -> str | None:
        return self._loop._strip_think(content)


class _LoopHookChain(AgentHook):
    """Run the core loop hook directly and isolate only extra hook failures."""

    def __init__(self, loop_hook: _LoopHook, extra_hooks: list[AgentHook]) -> None:
        self._loop_hook = loop_hook
        self._extra_hooks = CompositeHook(extra_hooks)

    def wants_streaming(self) -> bool:
        return self._loop_hook.wants_streaming() or self._extra_hooks.wants_streaming()

    async def before_iteration(self, context: AgentHookContext) -> None:
        await self._loop_hook.before_iteration(context)
        await self._extra_hooks.before_iteration(context)

    async def on_stream(self, context: AgentHookContext, delta: str) -> None:
        await self._loop_hook.on_stream(context, delta)
        await self._extra_hooks.on_stream(context, delta)

    async def on_stream_end(self, context: AgentHookContext, *, resuming: bool) -> None:
        await self._loop_hook.on_stream_end(context, resuming=resuming)
        await self._extra_hooks.on_stream_end(context, resuming=resuming)

    async def before_execute_tools(self, context: AgentHookContext) -> None:
        await self._loop_hook.before_execute_tools(context)
        await self._extra_hooks.before_execute_tools(context)

    async def after_iteration(self, context: AgentHookContext) -> None:
        await self._loop_hook.after_iteration(context)
        await self._extra_hooks.after_iteration(context)

    def finalize_content(self, context: AgentHookContext, content: str | None) -> str | None:
        content = self._loop_hook.finalize_content(context, content)
        return self._extra_hooks.finalize_content(context, content)


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

    _RUNTIME_CHECKPOINT_KEY = "runtime_checkpoint"
    _PENDING_USER_TURN_KEY = "pending_user_turn"

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int | None = None,
        context_window_tokens: int | None = None,
        context_block_limit: int | None = None,
        max_tool_result_chars: int | None = None,
        provider_retry_mode: str = "standard",
        web_config: WebToolsConfig | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        agents_config: AgentsConfig | None = None,
        timezone: str | None = None,
        session_ttl_minutes: int = 0,
        hooks: list[AgentHook] | None = None,
        fallback_models: list[str] | None = None,
        unified_session: bool = False,
        disabled_skills: list[str] | None = None,
        tools_config: ToolsConfig | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig, ToolsConfig, WebToolsConfig

        _tc = tools_config or ToolsConfig()
        defaults = AgentDefaults()
        self.bus = bus
        self.channels_config = channels_config
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = (
            max_iterations if max_iterations is not None else defaults.max_tool_iterations
        )
        self.context_window_tokens = (
            context_window_tokens
            if context_window_tokens is not None
            else defaults.context_window_tokens
        )
        self.context_block_limit = context_block_limit
        self.max_tool_result_chars = (
            max_tool_result_chars
            if max_tool_result_chars is not None
            else defaults.max_tool_result_chars
        )
        self.provider_retry_mode = provider_retry_mode
        self.web_config = web_config or WebToolsConfig()
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self._start_time = time.time()
        self._last_usage: dict[str, int] = {}
        self.fallback_models = fallback_models or []
        self.max_repeat_lookups = getattr(defaults, "max_repeat_lookups", 2)
        self._model_overrides: dict[str, str] = load_model_overrides()
        self._temperature_overrides: dict[str, float] = load_temperature_overrides()
        self._extra_hooks: list[AgentHook] = hooks or []
        self.stats_manager = StatsManager(workspace)

        self.context = ContextBuilder(workspace, timezone=timezone, disabled_skills=disabled_skills)
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.runner = AgentRunner(provider)
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            agents_config=agents_config,
            web_config=self.web_config,
            max_tool_result_chars=self.max_tool_result_chars,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            disabled_skills=disabled_skills,
        )
        self._unified_session = unified_session
        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stacks: dict[str, AsyncExitStack] = {}
        self._mcp_connected = False
        self._mcp_connecting = False
        self._active_tasks: dict[str, list[asyncio.Task]] = {}  # session_key -> tasks
        self._background_tasks: list[asyncio.Task] = []
        self._session_locks: dict[str, asyncio.Lock] = {}
        # Per-session pending queues for mid-turn message injection.
        self._pending_queues: dict[str, asyncio.Queue] = {}
        # NANOBOT_MAX_CONCURRENT_REQUESTS: <=0 means unlimited; default 3.
        _max = int(os.environ.get("NANOBOT_MAX_CONCURRENT_REQUESTS", "3"))
        self._concurrency_gate: asyncio.Semaphore | None = (
            asyncio.Semaphore(_max) if _max > 0 else None
        )
        self.consolidator = Consolidator(
            store=self.context.memory,
            provider=provider,
            model=self.model,
            sessions=self.sessions,
            context_window_tokens=self.context_window_tokens,
            build_messages=self.context.build_messages,
            get_tool_definitions=self.tools.get_definitions,
            max_completion_tokens=provider.generation.max_tokens,
        )
        self.memory_consolidator = self.consolidator
        self.auto_compact = AutoCompact(
            sessions=self.sessions,
            consolidator=self.consolidator,
            session_ttl_minutes=session_ttl_minutes,
        )
        self.dream = Dream(
            store=self.context.memory,
            provider=provider,
            model=self.model,
        )
        self._register_default_tools()
        if _tc.my.enable:
            self.tools.register(MyTool(loop=self, modify_allowed=_tc.my.allow_set))
        self._runtime_vars: dict[str, Any] = {}
        self._current_iteration: int = 0
        self.commands = CommandRouter()
        register_builtin_commands(self.commands)

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = (
            self.workspace if (self.restrict_to_workspace or self.exec_config.sandbox) else None
        )
        extra_read = [BUILTIN_SKILLS_DIR] if allowed_dir else None
        self.tools.register(
            ReadFileTool(
                workspace=self.workspace, allowed_dir=allowed_dir, extra_allowed_dirs=extra_read
            )
        )
        for cls in (WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        for cls in (GlobTool, GrepTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
        self.tools.register(SessionSearchTool(workspace=self.workspace))
        self.tools.register(SkillManageTool(workspace=self.workspace))
        self.tools.register(WorkflowListTool(workspace=self.workspace))
        self.tools.register(WorkflowRunTool(workspace=self.workspace))
        if self.exec_config.enable:
            self.tools.register(
                ExecTool(
                    working_dir=str(self.workspace),
                    timeout=self.exec_config.timeout,
                    restrict_to_workspace=self.restrict_to_workspace,
                    sandbox=self.exec_config.sandbox,
                    path_append=self.exec_config.path_append,
                    allowed_env_keys=self.exec_config.allowed_env_keys,
                )
            )
        if self.web_config.enable:
            self.tools.register(
                WebSearchTool(config=self.web_config.search, proxy=self.web_config.proxy)
            )
            self.tools.register(WebFetchTool(proxy=self.web_config.proxy))
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.tools.register(SpawnTool(manager=self.subagents))
        if self.cron_service:
            self.tools.register(
                CronTool(self.cron_service, default_timezone=self.context.timezone or "UTC")
            )

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanobot.agent.tools.mcp import connect_mcp_servers

        try:
            self._mcp_stacks = await connect_mcp_servers(self._mcp_servers, self.tools)
            if self._mcp_stacks:
                self._mcp_connected = True
            else:
                logger.warning("No MCP servers connected successfully (will retry next message)")
        except asyncio.CancelledError:
            logger.warning("MCP connection cancelled (will retry next message)")
            self._mcp_stacks.clear()
        except BaseException as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            self._mcp_stacks.clear()
        finally:
            self._mcp_connecting = False

    def _set_tool_context(
        self,
        channel: str,
        chat_id: str,
        message_id: str | None = None,
        thread_id: int | None = None,
        session_key: str | None = None,
    ) -> None:
        """Update context for all tools that need routing info."""
        model_override = self._model_overrides.get(session_key) if session_key else None
        effective_key = session_key or (
            UNIFIED_SESSION_KEY if self._unified_session else f"{channel}:{chat_id}"
        )
        for name in ("message", "spawn", "cron", "my", "session_search", "workflow_run"):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    if name == "message":
                        tool.set_context(channel, chat_id, message_id, thread_id)
                    elif name == "cron":
                        tool.set_context(channel, chat_id, thread_id)
                    elif name == "spawn":
                        tool.set_context(
                            channel,
                            chat_id,
                            effective_key=effective_key,
                            model_override=model_override,
                            thread_id=thread_id,
                        )
                    elif name in ("session_search", "workflow_run"):
                        tool.set_context(session_key=effective_key)
                    else:
                        tool.set_context(channel, chat_id)

    def _ordered_fallback_models(self, primary_model: str) -> list[str]:
        """Return de-duplicated fallback models in the order they should be tried."""
        ordered: list[str] = []
        seen = {primary_model}
        for candidate in self.fallback_models:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            ordered.append(candidate)
        return ordered

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        from nanobot.utils.helpers import strip_think

        return strip_think(text) or None

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hints with smart abbreviation."""
        from nanobot.utils.tool_hints import format_tool_hints

        return format_tool_hints(tool_calls)

    async def _dispatch_command_inline(
        self,
        msg: InboundMessage,
        key: str,
        raw: str,
        dispatch_fn: Callable[[CommandContext], Awaitable[OutboundMessage | None]],
    ) -> None:
        """Dispatch a command directly from the run() loop and publish the result."""
        ctx = CommandContext(msg=msg, session=None, key=key, raw=raw, loop=self)
        result = await dispatch_fn(ctx)
        if result:
            await self.bus.publish_outbound(result)
        else:
            logger.warning("Command '{}' matched but dispatch returned None", raw)

    async def _cancel_active_tasks(self, key: str) -> int:
        """Cancel and await all active tasks and subagents for *key*.

        Returns the total number of cancelled tasks + subagents.
        """
        tasks = self._active_tasks.pop(key, [])
        cancelled = sum(1 for t in tasks if not t.done() and t.cancel())
        for t in tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass
        sub_cancelled = await self.subagents.cancel_by_session(key)
        return cancelled + sub_cancelled

    def _effective_session_key(self, msg: InboundMessage) -> str:
        """Return the session key used for task routing and mid-turn injections."""
        if self._unified_session and not msg.session_key_override:
            return UNIFIED_SESSION_KEY
        return msg.session_key

    def _handle_model_command(
        self, msg: InboundMessage, session_key: str, raw_content: str | None = None
    ) -> OutboundMessage:
        """Handle /model command: show current model or set a session override."""
        raw = (raw_content or msg.content).strip()
        parts = raw.split(None, 2)
        model_arg = parts[1].strip() if len(parts) > 1 else ""
        _meta = dict(msg.metadata or {})
        _meta["command_response"] = True

        if model_arg.lower() == "temp":
            temp_arg = parts[2].strip() if len(parts) > 2 else ""
            return self._handle_temp_command(msg, session_key, temp_arg, _meta)

        if not model_arg:
            effective = self._model_overrides.get(session_key, self.model)
            is_override = session_key in self._model_overrides
            status = (
                f"🤖 Current model: `{effective}`"
                + (
                    "\n_(session override — use `/model reset` to revert to default)_"
                    if is_override
                    else ""
                )
                + "\n\nSwitch model with `/model <model-id>`."
            )
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=status,
                metadata=_meta,
            )

        if model_arg.lower() == "reset":
            removed = self._model_overrides.pop(session_key, None)
            if removed:
                save_model_overrides(self._model_overrides)
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=f"🔄 Model reset to default: `{self.model}`",
                    metadata=_meta,
                )
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"Already using the default model: `{self.model}`",
                metadata=_meta,
            )

        new_model = model_arg.strip("`")
        self._model_overrides[session_key] = new_model
        save_model_overrides(self._model_overrides)
        logger.info("Model switched to '{}' for session {}", new_model, session_key)
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=f"✅ Model switched to `{new_model}` for this session.\nUse `/model reset` to revert to default.",
            metadata=_meta,
        )

    def _handle_temp_command(
        self, msg: InboundMessage, session_key: str, temp_arg: str, _meta: dict
    ) -> OutboundMessage:
        """Handle /model temp subcommand: show or set a session temperature override."""
        if not temp_arg:
            effective_temp = self._temperature_overrides.get(session_key)
            is_override = session_key in self._temperature_overrides
            guidance = (
                "\n\n**Temperature Guidance:**\n"
                "| Task | Recommended Temp | Why? |\n"
                "|------|-----------------|------|\n"
                "| Stock Analysis | 0.0 - 0.2 | Precision, factual accuracy |\n"
                "| Coding / Technical | 0.2 - 0.4 | Deterministic, consistent |\n"
                "| General Chat | 0.7 | Balanced creativity |\n"
                "| Brainstorming | 0.9 - 1.2 | Maximum creativity |\n"
            )
            if is_override:
                status = f"🌡️ Current temperature: `{effective_temp}`\n_(session override — use `/model temp reset` to revert)_"
            else:
                status = "🌡️ Temperature: using model default (no override set)"
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=status + guidance + "\n\nSet temperature with `/model temp <value>`.",
                metadata=_meta,
            )

        if temp_arg.lower() == "reset":
            removed = self._temperature_overrides.pop(session_key, None)
            if removed is not None:
                save_temperature_overrides(self._temperature_overrides)
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="🔄 Temperature reset to model default.",
                    metadata=_meta,
                )
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="Temperature is already using model default.",
                metadata=_meta,
            )

        try:
            new_temp = float(temp_arg)
            if new_temp < 0 or new_temp > 2.0:
                return OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content="❌ Temperature must be between 0.0 and 2.0.",
                    metadata=_meta,
                )
        except ValueError:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=f"❌ Invalid temperature value: `{temp_arg}`. Use a number like `0.7`.",
                metadata=_meta,
            )

        self._temperature_overrides[session_key] = new_temp
        save_temperature_overrides(self._temperature_overrides)
        logger.info("Temperature set to {} for session {}", new_temp, session_key)
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=f"✅ Temperature set to `{new_temp}` for this session.\nUse `/model temp reset` to revert to default.",
            metadata=_meta,
        )

    async def _handle_stats_command(self, msg: InboundMessage, args: list[str]) -> OutboundMessage:
        """Handle /stats command for chat, topic, or global token usage."""
        _meta = dict(msg.metadata or {})
        _meta["command_response"] = True

        if args and args[0].lower() == "topic" and _meta.get("message_thread_id") is None:
            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content="❌ This command is only available in topic threads.",
                metadata=_meta,
            )

        if args and args[0].lower() == "all":
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
            response = "📊 Total Token Usage Statistics\n\n"
            response += f"• Total messages: {total_messages}\n"
            response += f"• Total tokens: {total_tokens:,}\n\n"
            for channel, stat in stats.items():
                response += (
                    f"📡 {channel}: {stat['total_tokens']:,} tokens ({stat['count']} messages)\n"
                )

            return OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=response,
                metadata=_meta,
            )

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

        response = "📊 Token Usage Statistics"
        if _meta.get("message_thread_id") is not None:
            response += f" (Topic {_meta.get('message_thread_id')})"
        else:
            response += " (This Chat)"
        response += "\n\n"
        response += f"• Total messages: {total_messages}\n"
        response += f"• Input tokens: {total_input:,}\n"
        response += f"• Output tokens: {total_output:,}\n"
        response += f"• Total tokens: {total_tokens:,}\n\n"

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=response,
            metadata=_meta,
        )

    async def run(self) -> None:
        """Run the agent loop, dispatching messages as tasks to stay responsive to /stop."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
            except asyncio.TimeoutError:
                self.auto_compact.check_expired(
                    self._schedule_background,
                    active_session_keys=self._pending_queues.keys(),
                )
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
                await self._dispatch_command_inline(
                    msg,
                    msg.session_key,
                    raw,
                    self.commands.dispatch_priority,
                )
                continue
            effective_key = self._effective_session_key(msg)
            if effective_key in self._pending_queues:
                # Non-priority commands must not be queued for injection;
                # dispatch them directly (same pattern as priority commands).
                if self.commands.is_dispatchable_command(raw):
                    await self._dispatch_command_inline(
                        msg,
                        effective_key,
                        raw,
                        self.commands.dispatch,
                    )
                    continue
                pending_msg = msg
                if effective_key != msg.session_key:
                    pending_msg = dataclasses.replace(msg, session_key_override=effective_key)
                try:
                    self._pending_queues[effective_key].put_nowait(pending_msg)
                except asyncio.QueueFull:
                    logger.warning(
                        "Pending queue full for session {}, falling back to queued task",
                        effective_key,
                    )
                else:
                    logger.info(
                        "Routed follow-up message to pending queue for session {}",
                        effective_key,
                    )
                    continue
            task = asyncio.create_task(self._dispatch(msg))
            self._active_tasks.setdefault(effective_key, []).append(task)
            task.add_done_callback(
                lambda t, k=effective_key: (
                    self._active_tasks.get(k, []) and self._active_tasks[k].remove(t)
                    if t in self._active_tasks.get(k, [])
                    else None
                )
            )

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[..., Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
        on_retry_wait: Callable[[str], Awaitable[None]] | None = None,
        *,
        session: Session | None = None,
        channel: str = "cli",
        chat_id: str = "direct",
        message_id: str | None = None,
        pending_queue: asyncio.Queue | None = None,
        thread_id: int | None = None,
        model_override: str | None = None,
        temperature_override: float | None = None,
        on_turn_saved: Callable[[list[dict]], Awaitable[None]] | None = None,
    ) -> tuple[str | None, list[str], list[dict], str, bool]:
        """Run the agent iteration loop.

        *on_stream*: called with each content delta during streaming.
        *on_stream_end(resuming)*: called when a streaming session finishes.
        ``resuming=True`` means tool calls follow (spinner should restart);
        ``resuming=False`` means this is the final response.
        *on_turn_saved*: callback triggered after each turn is saved incrementally.
        """
        effective_model = model_override or self.model
        # Derive session_key for tool context
        if session:
            session_key = session.key
        elif thread_id:
            session_key = f"{channel}:{chat_id}:topic:{thread_id}"
        else:
            session_key = f"{channel}:{chat_id}"

        loop_hook = _LoopHook(
            self,
            on_progress=on_progress,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
            channel=channel,
            chat_id=chat_id,
            message_id=message_id,
            thread_id=thread_id,
            session_key=session_key,
        )
        hook: AgentHook = (
            _LoopHookChain(loop_hook, self._extra_hooks) if self._extra_hooks else loop_hook
        )

        async def _checkpoint(payload: dict[str, Any]) -> None:
            if session is None:
                return
            self._set_runtime_checkpoint(session, payload)

        async def _drain_pending(*, limit: int = _MAX_INJECTIONS_PER_TURN) -> list[dict[str, Any]]:
            if pending_queue is None:
                return []
            items: list[dict[str, Any]] = []
            while len(items) < limit:
                try:
                    pending_msg = pending_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                user_content = self.context._build_user_content(
                    pending_msg.content,
                    pending_msg.media if pending_msg.media else None,
                )
                runtime_ctx = self.context._build_runtime_context(
                    pending_msg.channel,
                    pending_msg.chat_id,
                    self.context.timezone,
                    thread_id=pending_msg.metadata.get("message_thread_id"),
                )
                if isinstance(user_content, str):
                    merged: str | list[dict[str, Any]] = f"{runtime_ctx}\n\n{user_content}"
                else:
                    merged = [{"type": "text", "text": runtime_ctx}] + user_content
                items.append({"role": "user", "content": merged})
            return items

        # Try with fallback models if configured
        models_to_try = [effective_model] + self._ordered_fallback_models(effective_model)
        last_error: Exception | None = None

        if len(models_to_try) > 1:
            logger.debug("Fallback model chain for {}: {}", effective_model, models_to_try)

        for idx, model in enumerate(models_to_try):
            try:
                result = await self.runner.run(
                    AgentRunSpec(
                        initial_messages=initial_messages,
                        tools=self.tools,
                        model=model,
                        max_iterations=self.max_iterations,
                        max_tool_result_chars=self.max_tool_result_chars,
                        temperature=temperature_override,
                        hook=hook,
                        error_message="Sorry, I encountered an error calling the AI model.",
                        concurrent_tools=True,
                        workspace=self.workspace,
                        session_key=session.key if session else None,
                        context_window_tokens=self.context_window_tokens,
                        context_block_limit=self.context_block_limit,
                        provider_retry_mode=self.provider_retry_mode,
                        progress_callback=on_progress,
                        retry_wait_callback=on_retry_wait,
                        checkpoint_callback=_checkpoint,
                        max_repeat_lookups=self.max_repeat_lookups,
                        on_turn_saved=on_turn_saved,
                        injection_callback=_drain_pending,
                    )
                )
                self._last_usage = result.usage

                # Check for errors that should trigger fallback
                if result.stop_reason == "error":
                    error_content = (result.final_content or "").lower()
                    if self._is_fallback_eligible_error_str(error_content):
                        raise Exception(result.final_content or "Unknown error")

                # Success or non-fallback error
                if result.stop_reason == "max_iterations":
                    logger.warning("Max iterations ({}) reached", self.max_iterations)
                elif result.stop_reason == "error":
                    logger.error("LLM returned error: {}", (result.final_content or "")[:200])
                return (
                    result.final_content,
                    result.tools_used,
                    result.messages,
                    result.stop_reason,
                    result.had_injections,
                )

            except Exception as e:
                last_error = e
                error_msg = str(e).lower()

                # Check if this is a fallback-eligible error
                is_fallback_eligible = self._is_fallback_eligible_error_str(error_msg)

                if is_fallback_eligible and model != models_to_try[-1]:
                    next_model = models_to_try[idx + 1]
                    logger.warning(
                        "Model {} failed with: {}, trying fallback model {}",
                        model,
                        str(e)[:100],
                        next_model,
                    )
                    continue
                if is_fallback_eligible:
                    logger.error("All fallback models exhausted, last error: {}", str(e)[:200])
                    messages = list(initial_messages)
                    messages.append(
                        {
                            "role": "assistant",
                            "content": _PERSISTED_MODEL_ERROR_PLACEHOLDER,
                        }
                    )
                    return str(e), [], messages, "error", False
                raise

        # Should not reach here, but return error if it does
        return str(last_error) if last_error else "Unknown error", [], [], "error", False

    @staticmethod
    def _is_fallback_eligible_error_str(error_msg: str) -> bool:
        """Return True when the error should trigger fallback."""
        return (
            "provider returned error" in error_msg
            or "502" in error_msg
            or "503" in error_msg
            or "500" in error_msg
            or "400" in error_msg
            or "429" in error_msg
            or "temporarily unavailable" in error_msg
            or "timeout" in error_msg
            or "timed out" in error_msg
            or "404" in error_msg
            or "403" in error_msg
            or "not found" in error_msg
            or "invalid model" in error_msg
            or "allocationquota" in error_msg
            or "free tier" in error_msg
            or "exhausted" in error_msg
            or "database is locked" in error_msg
            or "bad_response" in error_msg
            or "unknown error" in error_msg
            or "bad_response_status_code" in error_msg
        )

    async def _dispatch(self, msg: InboundMessage) -> None:
        """Process a message: per-session serial, cross-session concurrent."""
        session_key = self._effective_session_key(msg)
        if session_key != msg.session_key:
            msg = dataclasses.replace(msg, session_key_override=session_key)
        lock = self._session_locks.setdefault(session_key, asyncio.Lock())
        gate = self._concurrency_gate or nullcontext()
        pending = asyncio.Queue(maxsize=20)
        self._pending_queues[session_key] = pending
        gate_limit: int | None = None
        if self._concurrency_gate is not None:
            gate_limit = getattr(self._concurrency_gate, "_value", 0) + len(
                getattr(self._concurrency_gate, "_waiters", []) or []
            )
        try:
            async with lock, gate:
                if self._concurrency_gate is not None:
                    current_value = getattr(self._concurrency_gate, "_value", 0)
                    active = max(0, (gate_limit or 0) - current_value)
                    logger.debug(
                        "Entered agent concurrency gate for session {}: active={}/{}",
                        session_key,
                        active,
                        gate_limit,
                    )
                try:
                    on_stream = on_stream_end = None
                    if msg.metadata.get("_wants_stream"):
                        stream_base_id = f"{msg.session_key}:{time.time_ns()}"
                        stream_segment = 0

                        def _current_stream_id() -> str:
                            return f"{stream_base_id}:{stream_segment}"

                        async def on_stream(delta: str) -> None:
                            meta = dict(msg.metadata or {})
                            meta["_stream_delta"] = True
                            meta["_stream_id"] = _current_stream_id()
                            await self.bus.publish_outbound(
                                OutboundMessage(
                                    channel=msg.channel,
                                    chat_id=msg.chat_id,
                                    content=delta,
                                    metadata=meta,
                                )
                            )

                        async def on_stream_end(*, resuming: bool = False) -> None:
                            nonlocal stream_segment
                            meta = dict(msg.metadata or {})
                            meta["_stream_end"] = True
                            meta["_resuming"] = resuming
                            meta["_stream_id"] = _current_stream_id()
                            await self.bus.publish_outbound(
                                OutboundMessage(
                                    channel=msg.channel,
                                    chat_id=msg.chat_id,
                                    content="",
                                    metadata=meta,
                                )
                            )
                            stream_segment += 1

                    response = await self._process_message(
                        msg,
                        on_stream=on_stream,
                        on_stream_end=on_stream_end,
                        pending_queue=pending,
                    )
                    if response is not None:
                        logger.debug(
                            "Publishing response to {}/{}", response.channel, response.chat_id
                        )
                        await self.bus.publish_outbound(response)
                    elif msg.channel == "cli":
                        await self.bus.publish_outbound(
                            OutboundMessage(
                                channel=msg.channel,
                                chat_id=msg.chat_id,
                                content="",
                                metadata=msg.metadata or {},
                            )
                        )
                    else:
                        logger.warning("No response to publish for {}/{}", msg.channel, msg.chat_id)
                except asyncio.CancelledError:
                    logger.info("Task cancelled for session {}", session_key)
                    # Preserve partial context from the interrupted turn so
                    # the user does not lose tool results and assistant
                    # messages accumulated before /stop.  The checkpoint was
                    # already persisted to session metadata by
                    # _emit_checkpoint during tool execution; materializing
                    # it into session history now makes it visible in the
                    # next conversation turn.
                    try:
                        key = self._effective_session_key(msg)
                        session = self.sessions.get_or_create(key)
                        if self._restore_runtime_checkpoint(session):
                            self._clear_pending_user_turn(session)
                            self.sessions.save(session)
                            logger.info(
                                "Restored partial context for cancelled session {}",
                                key,
                            )
                    except Exception:
                        logger.debug(
                            "Could not restore checkpoint for cancelled session {}",
                            session_key,
                            exc_info=True,
                        )
                    raise
                except Exception:
                    logger.exception("Error processing message for session {}", session_key)
                    await self.bus.publish_outbound(
                        OutboundMessage(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            content="Sorry, I encountered an error.",
                        )
                    )
                finally:
                    if self._concurrency_gate is not None:
                        current_value = getattr(self._concurrency_gate, "_value", 0)
                        active = max(0, (gate_limit or 0) - current_value - 1)
                        logger.debug(
                            "Released agent concurrency gate for session {}: active={}/{}",
                            session_key,
                            active,
                            gate_limit,
                        )
        finally:
            queue = self._pending_queues.pop(session_key, None)
            if queue is not None:
                leftover = 0
                while True:
                    try:
                        item = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    await self.bus.publish_inbound(item)
                    leftover += 1
                if leftover:
                    logger.info(
                        "Re-published {} leftover message(s) to bus for session {}",
                        leftover,
                        session_key,
                    )

    async def close_mcp(self) -> None:
        """Drain pending background archives, then close MCP connections."""
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
        for name, stack in self._mcp_stacks.items():
            try:
                await stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                logger.debug("MCP server '{}' cleanup error (can be ignored)", name)
        self._mcp_stacks.clear()

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
        pending_queue: asyncio.Queue | None = None,
        *,
        ephemeral_session: bool = False,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        # System messages: parse origin from chat_id ("channel:chat_id")
        if msg.channel == "system":
            channel, chat_id = (
                msg.chat_id.split(":", 1) if ":" in msg.chat_id else ("cli", msg.chat_id)
            )
            logger.info("Processing system message from {}", msg.sender_id)

            # Include topic in session key if thread_id is in metadata
            thread_id = msg.metadata.get("message_thread_id")
            logger.debug("System message metadata: {}, thread_id={}", msg.metadata, thread_id)
            if thread_id is not None:
                key = f"{channel}:{chat_id}:topic:{thread_id}"
            else:
                key = f"{channel}:{chat_id}"
            logger.debug("System message session key: {}", key)

            session = self.sessions.get_or_create(key)
            if self._restore_runtime_checkpoint(session):
                self.sessions.save(session)
            if self._restore_pending_user_turn(session):
                self.sessions.save(session)
            session, pending = self.auto_compact.prepare_session(session, key)
            await self.consolidator.maybe_consolidate_by_tokens(
                session,
                session_summary=pending,
            )
            # Persist subagent follow-ups into durable history BEFORE prompt
            # assembly. ContextBuilder merges adjacent same-role messages for
            # provider compatibility, which previously caused the follow-up to
            # disappear from session.messages while still being visible to the
            # LLM via the merged prompt. See _persist_subagent_followup.
            is_subagent = msg.sender_id == "subagent"
            if is_subagent and self._persist_subagent_followup(session, msg):
                self.sessions.save(session)
            self._set_tool_context(
                channel,
                chat_id,
                msg.metadata.get("message_id"),
                thread_id,
                session_key=key,
            )
            history = session.get_history(max_messages=0)
            current_role = "assistant" if is_subagent else "user"

            # Subagent content is already in `history` above; passing it again
            # as current_message would double-project it into the prompt.
            messages = self.context.build_messages(
                history=history,
                current_message="" if is_subagent else msg.content,
                channel=channel,
                chat_id=chat_id,
                thread_id=thread_id,
                session_summary=pending,
                current_role=current_role,
            )

            async def _on_turn_saved_sys(messages: list[dict]) -> None:
                self._save_turn(session, messages, 1 + len(history))
                self.sessions.save(session)

            run_result = await self._run_agent_loop(
                messages,
                session=session,
                channel=channel,
                chat_id=chat_id,
                message_id=msg.metadata.get("message_id"),
                thread_id=thread_id,
                model_override=self._model_overrides.get(key),
                temperature_override=self._temperature_overrides.get(key),
                on_turn_saved=_on_turn_saved_sys,
                pending_queue=pending_queue,
            )
            if len(run_result) >= 3:
                final_content, _, all_msgs = run_result[:3]
            else:
                raise ValueError("_run_agent_loop returned unexpected result shape")
            self._save_turn(session, all_msgs, 1 + len(history))
            self._clear_pending_user_turn(session)
            self._clear_runtime_checkpoint(session)
            self.sessions.save(session)
            self._schedule_background(self.consolidator.maybe_consolidate_by_tokens(session))
            is_cron = msg.channel == "cron"
            metadata = {}
            if thread_id is not None:
                metadata["message_thread_id"] = thread_id
            return OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=format_provider_error(final_content, is_cron=is_cron)
                or "Background task completed.",
                metadata=metadata,
            )

        # Extract document text from media at the processing boundary so all
        # channels benefit without format-specific logic in ContextBuilder.
        if msg.media:
            new_content, image_only = extract_documents(msg.content, msg.media)
            if dataclasses.is_dataclass(msg):
                msg = dataclasses.replace(msg, content=new_content, media=image_only)
            else:
                msg.content = new_content
                msg.media = image_only

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session: Session | None = None
        if not ephemeral_session:
            session = self.sessions.get_or_create(key)
        if session and self._restore_runtime_checkpoint(session):
            self.sessions.save(session)
        if session and self._restore_pending_user_turn(session):
            self.sessions.save(session)
        if session:
            session, pending = self.auto_compact.prepare_session(session, key)
        else:
            pending = None

        # Slash commands
        raw = msg.content.strip()
        if raw.startswith("@"):
            raw = re.sub(r"^@\S+\s*", "", raw).strip()
        ctx = CommandContext(msg=msg, session=session, key=key, raw=raw, loop=self)
        logger.debug("Dispatching command: raw={!r}", raw)
        if result := await self.commands.dispatch(ctx):
            logger.debug(
                "Command returned result: channel={}, chat_id={}", result.channel, result.chat_id
            )
            return result

        if session is not None:
            await self.consolidator.maybe_consolidate_by_tokens(
                session,
                session_summary=pending,
            )

        self._set_tool_context(
            msg.channel,
            msg.chat_id,
            msg.metadata.get("message_id"),
            msg.metadata.get("message_thread_id"),
            session_key=key,
        )
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        history = session.get_history(max_messages=0) if session else []
        initial_messages = self.context.build_messages(
            history=history,
            current_message=msg.content,
            session_summary=pending,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
            thread_id=msg.metadata.get("message_thread_id"),
        )

        async def _bus_progress(content: str, *, tool_hint: bool = False) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=content,
                    metadata=meta,
                )
            )

        async def _on_retry_wait(content: str) -> None:
            meta = dict(msg.metadata or {})
            meta["_retry_wait"] = True
            await self.bus.publish_outbound(
                OutboundMessage(
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=content,
                    metadata=meta,
                )
            )

        # Persist the triggering user message immediately, before running the
        # agent loop. If the process is killed mid-turn (OOM, SIGKILL, self-
        # restart, etc.), the existing runtime_checkpoint preserves the
        # in-flight assistant/tool state but NOT the user message itself, so
        # the user's prompt is silently lost on recovery. Saving it up front
        # makes recovery possible from the session log alone.
        user_persisted_early = False
        if session is not None and isinstance(msg.content, str) and msg.content.strip():
            session.add_message("user", msg.content)
            self._mark_pending_user_turn(session)
            self.sessions.save(session)
            user_persisted_early = True

        final_content, _, all_msgs, stop_reason, had_injections = await self._run_agent_loop(
            initial_messages,
            on_progress=on_progress or _bus_progress,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
            on_retry_wait=_on_retry_wait,
            session=session,
            channel=msg.channel,
            chat_id=msg.chat_id,
            message_id=msg.metadata.get("message_id"),
            thread_id=msg.metadata.get("message_thread_id"),
            model_override=self._model_overrides.get(key),
            temperature_override=self._temperature_overrides.get(key),
            pending_queue=pending_queue,
        )

        if final_content is None or not final_content.strip():
            final_content = EMPTY_FINAL_RESPONSE_MESSAGE

        if session is not None:
            save_skip = 1 + len(history) + (1 if user_persisted_early else 0)
            self._save_turn(session, all_msgs, save_skip)
            self._clear_pending_user_turn(session)
            self._clear_runtime_checkpoint(session)
            self.sessions.save(session)
            self._schedule_background(self.consolidator.maybe_consolidate_by_tokens(session))

        if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
            if not had_injections or stop_reason == "empty_final_response":
                return None

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)

        meta = dict(msg.metadata or {})
        if on_stream is not None and stop_reason != "error":
            meta["_streamed"] = True
            if is_provider_error_message(final_content):
                meta["_streamed_error"] = True
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=format_provider_error(final_content),
            metadata=meta,
        )

    def _sanitize_persisted_blocks(
        self,
        content: list[dict[str, Any]],
        *,
        should_truncate_text: bool = False,
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

            if block.get("type") == "image_url" and block.get("image_url", {}).get(
                "url", ""
            ).startswith("data:image/"):
                path = (block.get("_meta") or {}).get("path", "")
                filtered.append({"type": "text", "text": image_placeholder_text(path)})
                continue

            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text = block["text"]
                if should_truncate_text and len(text) > self.max_tool_result_chars:
                    text = truncate_text_fn(text, self.max_tool_result_chars)
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
                if isinstance(content, str) and len(content) > self.max_tool_result_chars:
                    entry["content"] = truncate_text_fn(content, self.max_tool_result_chars)
                elif isinstance(content, list):
                    filtered = self._sanitize_persisted_blocks(content, should_truncate_text=True)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            elif role == "user":
                if isinstance(content, str) and content.startswith(
                    ContextBuilder._RUNTIME_CONTEXT_TAG
                ):
                    end_marker = ContextBuilder._RUNTIME_CONTEXT_END
                    end_pos = content.find(end_marker)
                    if end_pos >= 0:
                        after = content[end_pos + len(end_marker) :].lstrip("\n")
                        if after:
                            entry["content"] = after
                        else:
                            continue
                    else:
                        after_tag = content[len(ContextBuilder._RUNTIME_CONTEXT_TAG) :].lstrip("\n")
                        if after_tag.strip():
                            entry["content"] = after_tag
                        else:
                            continue
                if isinstance(content, list):
                    filtered = self._sanitize_persisted_blocks(content, drop_runtime=True)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
        session.updated_at = datetime.now()

    def _persist_subagent_followup(self, session: Session, msg: InboundMessage) -> bool:
        """Persist subagent follow-ups before prompt assembly so history stays durable.

        Returns True if a new entry was appended; False if the follow-up was
        deduped (same ``subagent_task_id`` already in session) or carries no
        content worth persisting.
        """
        if not msg.content:
            return False
        task_id = msg.metadata.get("subagent_task_id") if isinstance(msg.metadata, dict) else None
        if task_id and any(
            m.get("injected_event") == "subagent_result" and m.get("subagent_task_id") == task_id
            for m in session.messages
        ):
            return False
        session.add_message(
            "assistant",
            msg.content,
            sender_id=msg.sender_id,
            injected_event="subagent_result",
            subagent_task_id=task_id,
        )
        return True

    def _set_runtime_checkpoint(self, session: Session, payload: dict[str, Any]) -> None:
        """Persist the latest in-flight turn state into session metadata."""
        session.metadata[self._RUNTIME_CHECKPOINT_KEY] = payload
        self.sessions.save(session)

    def _mark_pending_user_turn(self, session: Session) -> None:
        session.metadata[self._PENDING_USER_TURN_KEY] = True

    def _clear_pending_user_turn(self, session: Session) -> None:
        session.metadata.pop(self._PENDING_USER_TURN_KEY, None)

    def _clear_runtime_checkpoint(self, session: Session) -> None:
        if self._RUNTIME_CHECKPOINT_KEY in session.metadata:
            session.metadata.pop(self._RUNTIME_CHECKPOINT_KEY, None)

    @staticmethod
    def _checkpoint_message_key(message: dict[str, Any]) -> tuple[Any, ...]:
        return (
            message.get("role"),
            message.get("content"),
            message.get("tool_call_id"),
            message.get("name"),
            message.get("tool_calls"),
            message.get("reasoning_content"),
            message.get("thinking_blocks"),
        )

    def _restore_runtime_checkpoint(self, session: Session) -> bool:
        """Materialize an unfinished turn into session history before a new request."""
        from datetime import datetime

        checkpoint = session.metadata.get(self._RUNTIME_CHECKPOINT_KEY)
        if not isinstance(checkpoint, dict):
            return False

        assistant_message = checkpoint.get("assistant_message")
        completed_tool_results = checkpoint.get("completed_tool_results") or []
        pending_tool_calls = checkpoint.get("pending_tool_calls") or []

        restored_messages: list[dict[str, Any]] = []
        if isinstance(assistant_message, dict):
            restored = dict(assistant_message)
            restored.setdefault("timestamp", datetime.now().isoformat())
            restored_messages.append(restored)
        for message in completed_tool_results:
            if isinstance(message, dict):
                restored = dict(message)
                restored.setdefault("timestamp", datetime.now().isoformat())
                restored_messages.append(restored)
        for tool_call in pending_tool_calls:
            if not isinstance(tool_call, dict):
                continue
            tool_id = tool_call.get("id")
            name = ((tool_call.get("function") or {}).get("name")) or "tool"
            restored_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": name,
                    "content": "Error: Task interrupted before this tool finished.",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        overlap = 0
        max_overlap = min(len(session.messages), len(restored_messages))
        for size in range(max_overlap, 0, -1):
            existing = session.messages[-size:]
            restored = restored_messages[:size]
            if all(
                self._checkpoint_message_key(left) == self._checkpoint_message_key(right)
                for left, right in zip(existing, restored)
            ):
                overlap = size
                break
        session.messages.extend(restored_messages[overlap:])

        self._clear_pending_user_turn(session)
        self._clear_runtime_checkpoint(session)
        return True

    def _restore_pending_user_turn(self, session: Session) -> bool:
        from datetime import datetime

        if not session.metadata.get(self._PENDING_USER_TURN_KEY):
            return False

        if session.messages and session.messages[-1].get("role") == "user":
            session.messages.append(
                {
                    "role": "assistant",
                    "content": "Error: Task interrupted before a response was generated.",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            session.updated_at = datetime.now()

        self._clear_pending_user_turn(session)
        return True

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        media: list[str] | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
        thread_id: int | None = None,
        ephemeral_session: bool = False,
    ) -> OutboundMessage | None:
        """Process a message directly and return the outbound payload."""
        await self._connect_mcp()
        metadata = {"message_thread_id": thread_id} if thread_id is not None else {}
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            media=media or [],
            metadata=metadata,
        )
        kwargs = {
            "session_key": session_key,
            "on_progress": on_progress,
            "on_stream": on_stream,
            "on_stream_end": on_stream_end,
        }
        if ephemeral_session:
            kwargs["ephemeral_session"] = True
        return await self._process_message(msg, **kwargs)
