"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import dataclasses
<<<<<<< HEAD
import inspect
import json
=======
>>>>>>> origin/main
import os
import re
import time
from contextlib import AsyncExitStack, nullcontext, suppress
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from nanobot.agent import context as agent_context
from nanobot.agent import model_presets as preset_helpers
from nanobot.agent.autocompact import AutoCompact
from nanobot.agent.context import ContextBuilder
from nanobot.agent.hook import AgentHook, CompositeHook
from nanobot.agent.memory import Consolidator, Dream
<<<<<<< HEAD
from nanobot.agent.runner import (
    _MAX_INJECTIONS_PER_TURN,
    _PERSISTED_MODEL_ERROR_PLACEHOLDER,
    AgentRunner,
    AgentRunSpec,
)
from nanobot.agent.skills import BUILTIN_SKILLS_DIR
=======
from nanobot.agent.progress_hook import AgentProgressHook
from nanobot.agent.runner import _MAX_INJECTIONS_PER_TURN, AgentRunner, AgentRunSpec
>>>>>>> origin/main
from nanobot.agent.subagent import SubagentManager
from nanobot.agent.tools.context import RequestContext, bind_request_context, reset_request_context
from nanobot.agent.tools.file_state import FileStateStore, bind_file_states, reset_file_states
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.self import MyTool
<<<<<<< HEAD
from nanobot.agent.tools.session_search import SessionSearchTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.skill_manage import SkillManageTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.agent.tools.workflow import WorkflowListTool, WorkflowRunTool
=======
>>>>>>> origin/main
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.progress import build_bus_progress_callback
from nanobot.bus.queue import MessageBus
from nanobot.bus.runtime_events import (
    RuntimeEventBus,
    RuntimeEventPublisher,
    ensure_runtime_event_publisher,
)
from nanobot.command import CommandContext, CommandRouter, register_builtin_commands
<<<<<<< HEAD
from nanobot.config.paths import (
    load_model_overrides,
    load_temperature_overrides,
    save_model_overrides,
    save_temperature_overrides,
)
from nanobot.config.schema import AgentDefaults, ProviderConfig
=======
from nanobot.config.schema import AgentDefaults, ModelPresetConfig
>>>>>>> origin/main
from nanobot.providers.base import LLMProvider
from nanobot.providers.factory import ProviderSnapshot
from nanobot.security.workspace_access import (
    WorkspaceScopeResolver,
    bind_workspace_scope,
    reset_workspace_scope,
)
from nanobot.session import turn_continuation
from nanobot.session.goal_state import (
    goal_state_runtime_lines,
    runner_wall_llm_timeout_s,
    sustained_goal_active,
)
from nanobot.session.manager import Session, SessionManager
from nanobot.utils.document import extract_documents, reference_non_image_attachments
from nanobot.utils.helpers import image_placeholder_text
from nanobot.utils.helpers import truncate_text as truncate_text_fn
from nanobot.utils.image_generation_intent import image_generation_prompt
from nanobot.utils.llm_runtime import LLMRuntime
from nanobot.utils.runtime import (
    EMPTY_FINAL_RESPONSE_MESSAGE,
    SUSTAINED_GOAL_CONTINUE_PROMPT,
)
<<<<<<< HEAD
from nanobot.utils.runtime import (
    EMPTY_FINAL_RESPONSE_MESSAGE,
    format_provider_error,
    is_provider_error_message,
)
from nanobot.utils.stats import StatsManager
from nanobot.workflows.progress import WorkflowProgressManager
from nanobot.workflows.store import WorkflowStore

if TYPE_CHECKING:
    from nanobot.config.schema import (
        AgentsConfig,
        ChannelsConfig,
        ExecToolConfig,
        ToolsConfig,
        WebToolsConfig,
=======

if TYPE_CHECKING:
    from nanobot.config.schema import (
        ChannelsConfig,
        ProviderConfig,
        ToolsConfig,
>>>>>>> origin/main
    )
    from nanobot.cron.service import CronService


UNIFIED_SESSION_KEY = "unified:default"

class TurnState(Enum):
    RESTORE = auto()
    COMPACT = auto()
    COMMAND = auto()
    BUILD = auto()
    RUN = auto()
    SAVE = auto()
    RESPOND = auto()
    DONE = auto()


<<<<<<< HEAD
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
        metadata: dict[str, Any] | None = None,
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
        self._metadata = metadata or {}
        self._session_key = session_key
        self._stream_buf = ""
=======
@dataclass
class StateTraceEntry:
    state: TurnState
    started_at: float
    duration_ms: float
    event: str
    error: str | None = None
>>>>>>> origin/main


@dataclass
class TurnContext:
    msg: InboundMessage
    session_key: str
    state: TurnState
    turn_id: str
    session: Session | None = None

<<<<<<< HEAD
        prev_clean = self._loop._strip_message_time_prefix(strip_think(self._stream_buf))
        self._stream_buf += delta
        new_clean = self._loop._strip_message_time_prefix(strip_think(self._stream_buf))
        incremental = new_clean[len(prev_clean) :]
        if incremental and self._on_stream:
            await self._on_stream(incremental)
=======
    history: list[dict[str, Any]] = field(default_factory=list)
    initial_messages: list[dict[str, Any]] = field(default_factory=list)
>>>>>>> origin/main

    final_content: str | None = None
    tools_used: list[str] = field(default_factory=list)
    all_messages: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = ""
    had_injections: bool = False

    user_persisted_early: bool = False
    save_skip: int = 0

<<<<<<< HEAD
    async def before_execute_tools(self, context: AgentHookContext) -> None:
        if self._on_progress:
            if not self._on_stream and not context.streamed_content:
                thought = self._loop._strip_think(
                    context.response.content if context.response else None
                )
                if thought:
                    await self._on_progress(thought)
            tool_hint = self._loop._strip_think(self._loop._tool_hint(context.tool_calls))
            tool_events = [build_tool_event_start_payload(tc) for tc in context.tool_calls]
            await invoke_on_progress(
                self._on_progress,
                tool_hint,
                tool_hint=True,
                tool_events=tool_events,
            )
        for tc in context.tool_calls:
            args_str = json.dumps(tc.arguments, ensure_ascii=False)
            logger.info("Tool call: {}({})", tc.name, args_str[:200])
        set_tool_context = self._loop._set_tool_context
        params = inspect.signature(set_tool_context).parameters
        kwargs: dict[str, Any] = {"session_key": self._session_key}
        if "thread_id" in params:
            kwargs["thread_id"] = self._thread_id
        if "metadata" in params:
            kwargs["metadata"] = self._metadata
        self._loop._set_tool_context(
            self._channel,
            self._chat_id,
            self._message_id,
            **kwargs,
        )
=======
    outbound: OutboundMessage | None = None
    suppress_response: bool = False
>>>>>>> origin/main

    on_progress: Callable[..., Awaitable[None]] | None = None
    on_stream: Callable[[str], Awaitable[None]] | None = None
    on_stream_end: Callable[..., Awaitable[None]] | None = None
    on_retry_wait: Callable[[str], Awaitable[None]] | None = None

    pending_queue: asyncio.Queue | None = None
    pending_summary: str | None = None
    turn_wall_started_at: float = field(default_factory=time.time)
    visible_run_started_at: float | None = None
    turn_latency_ms: int | None = None

    trace: list[StateTraceEntry] = field(default_factory=list)


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

    @property
    def current_iteration(self) -> int:
        return self._current_iteration

    @property
    def tool_names(self) -> list[str]:
        return self.tools.tool_names

    def llm_runtime(self) -> LLMRuntime:
        """Return the current provider/model pair owned by this loop."""
        self._refresh_provider_snapshot()
        return LLMRuntime(self.provider, self.model)

    _RUNTIME_CHECKPOINT_KEY = "runtime_checkpoint"
    _PENDING_USER_TURN_KEY = "pending_user_turn"

    # Event-driven state transition table.
    # Handlers return an event string; the driver looks up the next state here.
    _TRANSITIONS: dict[tuple[TurnState, str], TurnState] = {
        (TurnState.RESTORE, "ok"): TurnState.COMPACT,
        (TurnState.COMPACT, "ok"): TurnState.COMMAND,
        (TurnState.COMMAND, "dispatch"): TurnState.BUILD,
        (TurnState.COMMAND, "shortcut"): TurnState.DONE,
        (TurnState.BUILD, "ok"): TurnState.RUN,
        (TurnState.RUN, "ok"): TurnState.SAVE,
        (TurnState.SAVE, "ok"): TurnState.RESPOND,
        (TurnState.RESPOND, "ok"): TurnState.DONE,
    }

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int | None = None,
        max_concurrent_subagents: int | None = None,
        context_window_tokens: int | None = None,
        context_block_limit: int | None = None,
        max_tool_result_chars: int | None = None,
        provider_retry_mode: str = "standard",
        tool_hint_max_length: int | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
        agents_config: AgentsConfig | None = None,
        timezone: str | None = None,
        session_ttl_minutes: int = 0,
        consolidation_ratio: float = 0.5,
        max_messages: int = 120,
        hooks: list[AgentHook] | None = None,
        fallback_models: list[str] | None = None,
        unified_session: bool = False,
        disabled_skills: list[str] | None = None,
        tools_config: ToolsConfig | None = None,
<<<<<<< HEAD
        image_generation_provider: ProviderConfig | None = None,
        enable_image_generation_tool: bool = False,
        provider_snapshot_loader: Callable[[], ProviderSnapshot] | None = None,
=======
        image_generation_provider_config: ProviderConfig | None = None,
        image_generation_provider_configs: dict[str, ProviderConfig] | None = None,
        provider_snapshot_loader: Callable[..., ProviderSnapshot] | None = None,
>>>>>>> origin/main
        provider_signature: tuple[object, ...] | None = None,
        model_presets: dict[str, ModelPresetConfig] | None = None,
        model_preset: str | None = None,
        preset_snapshot_loader: preset_helpers.PresetSnapshotLoader | None = None,
        runtime_events: RuntimeEventBus | None = None,
        runtime_model_publisher: Callable[[str, str | None], None] | None = None,
    ):
        from nanobot.config.schema import ToolsConfig

        _tc = tools_config or ToolsConfig()
        defaults = AgentDefaults()
        self.bus = bus
        self.runtime_events = runtime_events or RuntimeEventBus()
        self.runtime_event_publisher = RuntimeEventPublisher(self.runtime_events)
        self.channels_config = channels_config
        self.provider = provider
        self._provider_snapshot_loader = provider_snapshot_loader
        self._preset_snapshot_loader = preset_snapshot_loader
        self._runtime_model_publisher = runtime_model_publisher
        self._provider_signature = provider_signature
        self._default_selection_signature = preset_helpers.default_selection_signature(provider_signature)
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
<<<<<<< HEAD
        self.web_config = web_config or WebToolsConfig()
        self.exec_config = exec_config or ExecToolConfig()
        self.tools_config = _tc
        self.image_generation_provider = image_generation_provider
        self.enable_image_generation_tool = enable_image_generation_tool
=======
        self.tool_hint_max_length = (
            tool_hint_max_length if tool_hint_max_length is not None
            else defaults.tool_hint_max_length
        )
        self.tools_config = _tc
        self.web_config = _tc.web
        self.exec_config = _tc.exec
        self._image_generation_provider_configs = dict(image_generation_provider_configs or {})
        if (
            image_generation_provider_config is not None
            and "openrouter" not in self._image_generation_provider_configs
        ):
            self._image_generation_provider_configs["openrouter"] = image_generation_provider_config
>>>>>>> origin/main
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.workspace_scopes = WorkspaceScopeResolver(
            default_workspace=workspace,
            default_restrict_to_workspace=restrict_to_workspace,
        )
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
        # One file-read/write tracker per logical session. The tool registry is
        # shared by this loop, so tools resolve the active state via contextvars.
        self._file_state_store = FileStateStore()
        self.runner = AgentRunner(provider)
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
<<<<<<< HEAD
            agents_config=agents_config,
            web_config=self.web_config,
=======
            tools_config=_tc,
>>>>>>> origin/main
            max_tool_result_chars=self.max_tool_result_chars,
            restrict_to_workspace=restrict_to_workspace,
            disabled_skills=disabled_skills,
            max_iterations=self.max_iterations,
            max_concurrent_subagents=max_concurrent_subagents,
            llm_wall_timeout_for_session=lambda sk: runner_wall_llm_timeout_s(self.sessions, sk),
        )
        self._unified_session = unified_session
        self._max_messages = max_messages if max_messages > 0 else 120
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
            consolidation_ratio=consolidation_ratio,
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
<<<<<<< HEAD
        self._workflow_progress = WorkflowProgressManager(WorkflowStore(self.workspace))
=======
        self.model_presets: dict[str, ModelPresetConfig] = model_presets or {}
        self._active_preset: str | None = None
        if model_preset:
            self.set_model_preset(model_preset, publish_update=False)
>>>>>>> origin/main
        self._register_default_tools()
        self._runtime_vars: dict[str, Any] = {}
        self._current_iteration: int = 0
        self.commands = CommandRouter()
        register_builtin_commands(self.commands)

<<<<<<< HEAD
    @staticmethod
    def _strip_message_time_prefix(content: str) -> str:
        """Remove model-copied history timestamp metadata from assistant output."""
        if not isinstance(content, str):
            return content
        return re.sub(r"^(?:\[Message Time: [^\]\n]+\](?:\n+|$))+", "", content).lstrip("\n")
=======
    @classmethod
    def from_config(
        cls,
        config: Any,
        bus: MessageBus | None = None,
        **extra: Any,
    ) -> AgentLoop:
        """Create an AgentLoop from config with the common parameter set.

        Extra keyword arguments are forwarded to ``AgentLoop.__init__``,
        allowing callers to override or extend the standard config-derived
        parameters (e.g. ``cron_service``, ``session_manager``).
        """
        from nanobot.providers.factory import make_provider

        if bus is None:
            bus = MessageBus()
        defaults = config.agents.defaults
        provider = extra.pop("provider", None) or make_provider(config)
        resolved = config.resolve_preset()
        model = extra.pop("model", None) or resolved.model
        context_window_tokens = extra.pop("context_window_tokens", None) or resolved.context_window_tokens
        provider_snapshot_loader = extra.pop("provider_snapshot_loader", None)
        preset_snapshot_loader = extra.pop("preset_snapshot_loader", None) or preset_helpers.make_preset_snapshot_loader(
            config,
            provider_snapshot_loader,
        )
        return cls(
            bus=bus,
            provider=provider,
            workspace=config.workspace_path,
            model=model,
            max_iterations=defaults.max_tool_iterations,
            max_concurrent_subagents=defaults.max_concurrent_subagents,
            context_window_tokens=context_window_tokens,
            context_block_limit=defaults.context_block_limit,
            max_tool_result_chars=defaults.max_tool_result_chars,
            provider_retry_mode=defaults.provider_retry_mode,
            tool_hint_max_length=defaults.tool_hint_max_length,
            restrict_to_workspace=config.tools.restrict_to_workspace,
            mcp_servers=config.tools.mcp_servers,
            channels_config=config.channels,
            timezone=defaults.timezone,
            unified_session=defaults.unified_session,
            disabled_skills=defaults.disabled_skills,
            session_ttl_minutes=defaults.session_ttl_minutes,
            consolidation_ratio=defaults.consolidation_ratio,
            max_messages=defaults.max_messages,
            tools_config=config.tools,
            model_presets=preset_helpers.configured_model_presets(config),
            model_preset=defaults.model_preset,
            provider_snapshot_loader=provider_snapshot_loader,
            preset_snapshot_loader=preset_snapshot_loader,
            **extra,
        )
>>>>>>> origin/main

    def _sync_subagent_runtime_limits(self) -> None:
        """Keep subagent runtime limits aligned with mutable loop settings."""
        self.subagents.max_iterations = self.max_iterations

    def _apply_provider_snapshot(
        self,
        snapshot: ProviderSnapshot,
        *,
        publish_update: bool = True,
        model_preset: str | None = None,
    ) -> None:
        """Swap model/provider for future turns without disturbing an active one."""
        provider = snapshot.provider
        model = snapshot.model
        context_window_tokens = snapshot.context_window_tokens
        old_model = self.model
        self.provider = provider
        self.model = model
        self.context_window_tokens = context_window_tokens
        self.runner.provider = provider
        self.subagents.set_provider(provider, model)
        self.consolidator.set_provider(provider, model, context_window_tokens)
        self.dream.set_provider(provider, model)
        self._provider_signature = snapshot.signature
        if publish_update and self._runtime_model_publisher is not None:
            self._runtime_model_publisher(
                self.model,
                model_preset if model_preset is not None else self.model_preset,
            )
        if publish_update:
            self._runtime_events().runtime_model_changed(
                self.model,
                model_preset if model_preset is not None else self.model_preset,
            )
        logger.info("Runtime model switched for next turn: {} -> {}", old_model, model)

    def _refresh_provider_snapshot(self) -> None:
        if self._provider_snapshot_loader is None:
            return
        try:
            snapshot = self._provider_snapshot_loader()
        except Exception:
            logger.exception("Failed to refresh provider config")
            return
        default_selection = preset_helpers.default_selection_signature(snapshot.signature)
        if self._active_preset and self._default_selection_signature in (None, default_selection):
            self._default_selection_signature = default_selection
            try:
                snapshot = self._build_model_preset_snapshot(self._active_preset)
            except Exception:
                logger.exception("Failed to refresh active model preset")
                return
        else:
            self._active_preset = None
            self._default_selection_signature = default_selection
        if snapshot.signature == self._provider_signature:
            return
        self._default_selection_signature = preset_helpers.default_selection_signature(snapshot.signature)
        self._apply_provider_snapshot(snapshot)

    @property
    def model_preset(self) -> str | None:
        return self._active_preset

    @model_preset.setter
    def model_preset(self, name: str | None) -> None:
        self.set_model_preset(name)

    def _build_model_preset_snapshot(self, name: str) -> ProviderSnapshot:
        return preset_helpers.build_runtime_preset_snapshot(
            name=name,
            presets=self.model_presets,
            provider=self.provider,
            loader=self._preset_snapshot_loader,
        )

    def set_model_preset(self, name: str | None, *, publish_update: bool = True) -> None:
        """Resolve a preset by name and apply all runtime model dependents."""
        name = preset_helpers.normalize_preset_name(name, self.model_presets)
        snapshot = self._build_model_preset_snapshot(name)
        self._apply_provider_snapshot(snapshot, publish_update=publish_update, model_preset=name)
        self._active_preset = name

    def _register_default_tools(self) -> None:
        """Register the default set of tools via plugin loader."""
        from nanobot.agent.tools.context import ToolContext
        from nanobot.agent.tools.loader import ToolLoader

        ctx = ToolContext(
            config=self.tools_config,
            workspace=str(self.workspace),
            bus=self.bus,
            subagent_manager=self.subagents,
            cron_service=self.cron_service,
            sessions=self.sessions,
            provider_snapshot_loader=self._provider_snapshot_loader,
            image_generation_provider_configs=self._image_generation_provider_configs,
            timezone=self.context.timezone or "UTC",
            workspace_sandbox=self.workspace_scopes.sandbox_status,
            runtime_events=self.runtime_events,
        )
<<<<<<< HEAD
        extra_read = [BUILTIN_SKILLS_DIR] if allowed_dir else None
        self.tools.register(AskUserTool())
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
        self.tools.register(WorkflowRunTool(workspace=self.workspace, progress=self._workflow_progress))
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
                WebSearchTool(
                    config=self.web_config.search,
                    proxy=self.web_config.proxy,
                    user_agent=self.web_config.user_agent,
                )
            )
            self.tools.register(
                WebFetchTool(
                    config=self.web_config.fetch,
                    proxy=self.web_config.proxy,
                    user_agent=self.web_config.user_agent,
                )
            )
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound, workspace=self.workspace))
        image_cfg = self.tools_config.image_generation
        image_provider = self.image_generation_provider
        if (
            self.enable_image_generation_tool
            and image_cfg.enabled
            and image_provider
            and image_provider.api_key
        ):
            from nanobot.agent.tools.image_generation import GenerateImageTool
            from nanobot.image_generation import ImageGenerationService

            service = ImageGenerationService(
                api_key=image_provider.api_key,
                api_base=image_provider.api_base,
                model=image_cfg.model,
                size=image_cfg.size,
                quality=image_cfg.quality,
                workspace=self.workspace,
            )
            self.tools.register(
                GenerateImageTool(service=service, send_callback=self.bus.publish_outbound)
            )
        self.tools.register(SpawnTool(manager=self.subagents))
        if self.cron_service:
            self.tools.register(
                CronTool(self.cron_service, default_timezone=self.context.timezone or "UTC")
=======
        loader = ToolLoader()
        registered = loader.load(ctx, self.tools)

        # MyTool needs runtime state reference — manual registration
        if self.tools_config.my.enable:
            self.tools.register(
                MyTool(runtime_state=self, modify_allowed=self.tools_config.my.allow_set)
>>>>>>> origin/main
            )
            registered.append("my")

        logger.info("Registered {} tools: {}", len(registered), registered)

    async def _connect_mcp(self) -> None:
        """Connect configured MCP servers."""
        await agent_context.connect_mcp(self, self.tools)

    def _set_tool_context(
        self,
        channel: str,
        chat_id: str,
        message_id: str | None = None,
        thread_id: int | None = None,
        metadata: dict | None = None,
        session_key: str | None = None,
    ) -> None:
        """Update context for all tools that need routing info."""
<<<<<<< HEAD
        # When the caller threads a thread-scoped session_key, honor it so
        # spawn announces route back to the originating thread session.
        metadata = dict(metadata or {})
        if thread_id is not None:
            metadata.setdefault("message_thread_id", thread_id)
=======
        from nanobot.agent.tools.context import ContextAware

>>>>>>> origin/main
        if session_key is not None:
            effective_key = session_key
        elif self._unified_session:
            effective_key = UNIFIED_SESSION_KEY
        else:
            effective_key = f"{channel}:{chat_id}"
<<<<<<< HEAD
        model_override = self._model_overrides.get(effective_key)
        for name in (
            "message",
            "generate_image",
            "spawn",
            "cron",
            "my",
            "session_search",
            "workflow_run",
        ):
            if tool := self.tools.get(name):
                if hasattr(tool, "set_context"):
                    if name in ("message", "generate_image"):
                        tool.set_context(channel, chat_id, message_id, thread_id, metadata=metadata)
                    elif name == "cron":
                        params = inspect.signature(tool.set_context).parameters
                        kwargs = {"metadata": metadata, "session_key": effective_key}
                        if "thread_id" in params:
                            kwargs["thread_id"] = thread_id
                        tool.set_context(channel, chat_id, **kwargs)
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
=======

        request_ctx = RequestContext(
            channel=channel,
            chat_id=chat_id,
            message_id=message_id,
            session_key=effective_key,
            metadata=dict(metadata or {}),
        )
>>>>>>> origin/main

        for name in self.tools.tool_names:
            tool = self.tools.get(name)
            if tool and isinstance(tool, ContextAware):
                tool.set_context(request_ctx)

    @staticmethod
    def _runtime_chat_id(msg: InboundMessage) -> str:
        """Return the chat id shown in runtime metadata for the model."""
        return str(msg.metadata.get("context_chat_id") or msg.chat_id)

    async def _build_bus_progress_callback(
        self, msg: InboundMessage
    ) -> Callable[..., Awaitable[None]]:
        """Build a progress callback that publishes to the message bus."""
        return build_bus_progress_callback(self.bus, msg)

    async def _build_retry_wait_callback(
        self, msg: InboundMessage
    ) -> Callable[[str], Awaitable[None]]:
        """Build a retry-wait callback that publishes to the message bus."""

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

        return _on_retry_wait

    def _runtime_events(self) -> RuntimeEventPublisher:
        return ensure_runtime_event_publisher(self)

    def _persist_user_message_early(
        self,
        msg: InboundMessage,
        session: Session,
        **kwargs: Any,
    ) -> bool:
        """Persist the triggering user message before the turn starts.

        Returns True if the message was persisted.
        """
        if not turn_continuation.should_persist_user_message(msg.metadata):
            return False
        media_paths = [p for p in (msg.media or []) if isinstance(p, str) and p]
        has_text = isinstance(msg.content, str) and msg.content.strip()
        if has_text or media_paths:
            extra: dict[str, Any] = ({"media": list(media_paths)} if media_paths else {}) | agent_context.session_extra(msg.metadata)
            extra.update(kwargs)
            text = msg.content if isinstance(msg.content, str) else ""
            session.add_message("user", text, **extra)
            self._mark_pending_user_turn(session)
            self.sessions.save(session)
            return True
        return False

    def _build_initial_messages(
        self,
        msg: InboundMessage,
        session: Session,
        history: list[dict[str, Any]],
        pending_summary: str | None,
    ) -> list[dict[str, Any]]:
        """Build the initial message list for the LLM turn."""
        scope = self.workspace_scopes.for_message(msg, session.metadata)
        return self.context.build_messages(
            history=history,
            current_message=image_generation_prompt(msg.content, msg.metadata),
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=self._runtime_chat_id(msg),
            sender_id=msg.sender_id,
            session_summary=pending_summary,
            session_metadata=session.metadata,
            workspace=scope.project_path,
            runtime_state=self,
            inbound_message=msg,
        )

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
            with suppress(asyncio.CancelledError, Exception):
                await t
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

    def _replay_token_budget(self) -> int:
        """Derive a token budget for session history replay from the context window."""
        if self.context_window_tokens <= 0:
            return 0
        max_output = getattr(getattr(self.provider, "generation", None), "max_tokens", 4096)
        try:
            reserved_output = int(max_output)
        except (TypeError, ValueError):
            reserved_output = 4096
        budget = self.context_window_tokens - max(1, reserved_output) - 1024
        return budget if budget > 0 else max(128, self.context_window_tokens // 2)

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

<<<<<<< HEAD
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
=======
        *on_stream*: called with each content delta during streaming.
        *on_stream_end(resuming)*: called when a streaming session finishes.
        ``resuming=True`` means tool calls follow (spinner should restart);
        ``resuming=False`` means this is the final response.

        Returns (final_content, tools_used, messages, stop_reason, had_injections).
        """
        self._sync_subagent_runtime_limits()

        loop_hook = AgentProgressHook(
            on_progress=on_progress,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
            channel=channel,
            chat_id=chat_id,
            message_id=message_id,
            metadata=metadata,
            session_key=session_key,
            tool_hint_max_length=self.tool_hint_max_length,
            set_tool_context=self._set_tool_context,
            on_iteration=lambda iteration: setattr(self, "_current_iteration", iteration),
        )
        hook: AgentHook = (
            CompositeHook([loop_hook] + self._extra_hooks) if self._extra_hooks else loop_hook
        )

        async def _checkpoint(payload: dict[str, Any]) -> None:
            if session is None:
                return
            self._set_runtime_checkpoint(session, payload)

        async def _drain_pending(*, limit: int = _MAX_INJECTIONS_PER_TURN) -> list[dict[str, Any]]:
            """Drain follow-up messages from the pending queue.

            When no messages are immediately available but sub-agents
            spawned in this dispatch are still running, blocks until at
            least one result arrives (or timeout).  This keeps the runner
            loop alive so subsequent sub-agent completions are consumed
            in-order rather than dispatched separately.
            """
            if pending_queue is None:
                return []

            def _to_user_message(pending_msg: InboundMessage) -> dict[str, Any]:
                content = pending_msg.content
                media = pending_msg.media if pending_msg.media else None
                if media:
                    content, media = self._prepare_message_media(content, media)
                    media = media or None
                user_content = self.context._build_user_content(content, media)
                return {"role": "user", "content": user_content}
>>>>>>> origin/main

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

<<<<<<< HEAD
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
=======
        active_session_key = session.key if session else session_key
        effective_scope = self.workspace_scopes.for_turn(
            channel=channel,
            message_metadata=metadata,
            session_metadata=session.metadata if session is not None else None,
        )
        request_ctx = RequestContext(
            channel=channel,
            chat_id=chat_id,
            message_id=message_id,
            session_key=active_session_key,
            metadata=dict(metadata or {}),
        )
        file_state_token = bind_file_states(self._file_state_store.for_session(active_session_key))
        request_token = bind_request_context(request_ctx)
        workspace_token = bind_workspace_scope(effective_scope)
        # Build continuation message that embeds the active goal objective so
        # the LLM can see it even if earlier Runtime Context was truncated.
        _goal_lines = goal_state_runtime_lines(session.metadata if session is not None else None)
        _goal_continue = (
            "You have an active sustained goal:\n\n"
            + "\n".join(_goal_lines)
            + "\n\nPlease continue working toward the objective using your tools, "
            "or call complete_goal if the work is truly finished."
        ) if _goal_lines else SUSTAINED_GOAL_CONTINUE_PROMPT
        session_metadata = session.metadata if session is not None else None
        try:
            result = await self.runner.run(AgentRunSpec(
                initial_messages=initial_messages,
                tools=self.tools,
                model=self.model,
                max_iterations=self.max_iterations,
                max_tool_result_chars=self.max_tool_result_chars,
                hook=hook,
                error_message="Sorry, I encountered an error calling the AI model.",
                concurrent_tools=True,
                workspace=effective_scope.project_path,
                session_key=session.key if session else None,
                context_window_tokens=self.context_window_tokens,
                context_block_limit=self.context_block_limit,
                provider_retry_mode=self.provider_retry_mode,
                progress_callback=on_progress,
                stream_progress_deltas=on_stream is not None,
                retry_wait_callback=on_retry_wait,
                checkpoint_callback=_checkpoint,
                injection_callback=_drain_pending,
                # Sustained goals may legitimately exceed NANOBOT_LLM_TIMEOUT_S; idle stall
                # is still capped by NANOBOT_STREAM_IDLE_TIMEOUT_S in streaming providers.
                llm_timeout_s=runner_wall_llm_timeout_s(
                    self.sessions,
                    session.key if session is not None else session_key,
                    metadata=session_metadata,
                    message_metadata=metadata,
                ),
                goal_active_predicate=lambda: sustained_goal_active(session.metadata) if session is not None else False,
                goal_continue_message=_goal_continue,
            ))
        finally:
            reset_workspace_scope(workspace_token)
            reset_request_context(request_token)
            reset_file_states(file_state_token)
        self._last_usage = result.usage
        if result.stop_reason == "max_iterations":
            logger.warning("Max iterations ({}) reached", self.max_iterations)
            should_stream = turn_continuation.should_stream_budget_response(
                stop_reason=result.stop_reason,
                pending_queue_available=pending_queue is not None and session is not None,
                session_metadata=session_metadata,
                message_metadata=metadata,
            )
            # Push final content through stream so streaming channels (e.g. Feishu)
            # update the card instead of leaving it empty.
            if on_stream and on_stream_end and should_stream:
                await on_stream(result.final_content or "")
                await on_stream_end(resuming=False)
        elif result.stop_reason == "error":
            logger.error("LLM returned error: {}", (result.final_content or "")[:200])
        return result.final_content, result.tools_used, result.messages, result.stop_reason, result.had_injections
>>>>>>> origin/main

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
            effective_key = self._effective_session_key(msg)
            if await agent_context.handle_runtime_control(self, msg, self.tools):
                continue
            if self.commands.is_priority(raw):
                await self._dispatch_command_inline(
<<<<<<< HEAD
                    msg,
                    msg.session_key,
                    raw,
                    self.commands.dispatch_priority,
                )
                continue
            effective_key = self._effective_session_key(msg)
=======
                    msg, effective_key, raw,
                    self.commands.dispatch_priority,
                )
                continue
            # If this session already has an active pending queue (i.e. a task
            # is processing this session), route the message there for mid-turn
            # injection instead of creating a competing task.
>>>>>>> origin/main
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
        metadata: dict[str, Any] | None = None,
        session_key: str | None = None,
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
        self._sync_subagent_runtime_limits()
        effective_model = model_override or self.model
        # Derive session_key for tool context
        if session_key:
            pass
        elif session:
            session_key = session.key
        elif thread_id:
            session_key = f"{channel}:{chat_id}:topic:{thread_id}"
        else:
            session_key = f"{channel}:{chat_id}"
        if thread_id is None and metadata:
            thread_id = metadata.get("message_thread_id")

        loop_hook = _LoopHook(
            self,
            on_progress=on_progress,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
            channel=channel,
            chat_id=chat_id,
            message_id=message_id,
            thread_id=thread_id,
            metadata=metadata,
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
            """Drain queued follow-up messages and wait for subagent completions when needed."""
            if pending_queue is None:
                return []

            def _to_user_message(pending_msg: InboundMessage) -> dict[str, Any]:
                content = pending_msg.content
                media = pending_msg.media if pending_msg.media else None
                if media:
                    content, media = extract_documents(content, media)
                    media = media or None
                user_content = self.context._build_user_content(content, media)
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
                return {"role": "user", "content": merged}

            items: list[dict[str, Any]] = []
            while len(items) < limit:
                try:
                    items.append(_to_user_message(pending_queue.get_nowait()))
                except asyncio.QueueEmpty:
                    break

            if (
                not items
                and session is not None
                and self.subagents.get_running_count_by_session(session.key) > 0
            ):
                try:
                    items.append(_to_user_message(await asyncio.wait_for(pending_queue.get(), timeout=300)))
                except asyncio.TimeoutError:
                    logger.warning(
                        "Timeout waiting for sub-agent completion in session {}",
                        session.key,
                    )
                    return items
                while len(items) < limit:
                    try:
                        items.append(_to_user_message(pending_queue.get_nowait()))
                    except asyncio.QueueEmpty:
                        break
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
<<<<<<< HEAD
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
=======

        pending: asyncio.Queue | None = None
        try:
            async with lock, gate:
                # Only the task that owns the session lock may publish the
                # active mid-turn injection queue for this session.
                pending = asyncio.Queue(maxsize=20)
                self._pending_queues[session_key] = pending
>>>>>>> origin/main
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
                    completed_channel = msg.channel
                    completed_chat_id = msg.chat_id
                    if response is not None:
                        logger.debug(
                            "Publishing response to {}/{}", response.channel, response.chat_id
                        )
                        await self.bus.publish_outbound(response)
                        completed_channel = response.channel
                        completed_chat_id = response.chat_id
                    elif msg.channel == "cli":
<<<<<<< HEAD
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
=======
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel, chat_id=msg.chat_id,
                            content="", metadata=msg.metadata or {},
                        ))
                    continuing = turn_continuation.internal_continuation_pending(msg.metadata)
                    if not continuing:
                        await self._runtime_events().turn_completed(
                            channel=completed_channel,
                            chat_id=completed_chat_id,
                            session_key=session_key,
                            metadata=msg.metadata,
                        )
>>>>>>> origin/main
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
<<<<<<< HEAD
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
=======
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel, chat_id=msg.chat_id,
                        content="Sorry, I encountered an error.",
                    ))
                    if not turn_continuation.internal_continuation_pending(msg.metadata):
                        await self._runtime_events().turn_completed(
                            channel=msg.channel,
                            chat_id=msg.chat_id,
                            session_key=session_key,
                            metadata=msg.metadata,
                        )
                finally:
                    # Drain any messages still in the pending queue and re-publish
                    # them to the bus so they are processed as fresh inbound messages
                    # rather than silently lost.  Only remove our own queue; a
                    # later task waiting on the lock must not be able to steal
                    # cleanup ownership.
                    queue = None
                    if self._pending_queues.get(session_key) is pending:
                        queue = self._pending_queues.pop(session_key, None)
                    else:
                        queue = pending
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
                                leftover, session_key,
                            )
                    if not turn_continuation.internal_continuation_pending(msg.metadata):
                        await self._runtime_events().run_status_changed(
                            msg, session_key, "idle"
                        )
                        self._runtime_events().clear_turn(session_key)
        finally:
            if pending is None:
                await self._runtime_events().run_status_changed(
                    msg, session_key, "idle"
                )
                self._runtime_events().clear_turn(session_key)
>>>>>>> origin/main

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

    async def _process_system_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[..., Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
        pending_queue: asyncio.Queue | None = None,
    ) -> OutboundMessage | None:
        """Process a system inbound message (e.g. subagent announce)."""
        channel, chat_id = (
            msg.chat_id.split(":", 1) if ":" in msg.chat_id else ("cli", msg.chat_id)
        )
        logger.info("Processing system message from {}", msg.sender_id)
        key = msg.session_key_override or f"{channel}:{chat_id}"
        session = self.sessions.get_or_create(key)
        if self._restore_runtime_checkpoint(session):
            self.sessions.save(session)
        if self._restore_pending_user_turn(session):
            self.sessions.save(session)

        session, pending = self.auto_compact.prepare_session(session, key)
        if pending:
            logger.info("Memory compact triggered for session {}", key)

        await self.consolidator.maybe_consolidate_by_tokens(
            session,
            replay_max_messages=self._max_messages,
        )
        is_subagent = msg.sender_id == "subagent"
        if is_subagent and self._persist_subagent_followup(session, msg):
            logger.debug("Subagent result persisted for session {}", key)
            self.sessions.save(session)
        self._set_tool_context(
            channel, chat_id, msg.metadata.get("message_id"),
            msg.metadata, session_key=key,
        )
        _hist_kwargs: dict[str, Any] = {
            "max_messages": self._max_messages,
            "max_tokens": self._replay_token_budget(),
            "include_timestamps": True,
        }
        history = session.get_history(**_hist_kwargs)
        current_role = "assistant" if is_subagent else "user"
        workspace_scope = self.workspace_scopes.for_message(msg, session.metadata)

        messages = self.context.build_messages(
            history=history,
            current_message="" if is_subagent else msg.content,
            channel=channel,
            chat_id=chat_id,
            current_role=current_role,
            sender_id=msg.sender_id,
            session_summary=pending,
            session_metadata=session.metadata,
            workspace=workspace_scope.project_path,
            runtime_state=self,
            inbound_message=msg,
            skip_runtime_lines=is_subagent,
        )
        t_wall = time.time()
        final_content, _, all_msgs, stop_reason, _ = await self._run_agent_loop(
            messages, session=session, channel=channel, chat_id=chat_id,
            message_id=msg.metadata.get("message_id"),
            metadata=msg.metadata,
            session_key=key,
            pending_queue=pending_queue,
        )
        wall_done = time.time()
        latency_ms = max(0, int((wall_done - t_wall) * 1000))
        self._save_turn(session, all_msgs, 1 + len(history), turn_latency_ms=latency_ms)
        self._runtime_events().record_turn_latency(key, latency_ms)
        session.enforce_file_cap(on_archive=self.context.memory.raw_archive)
        self._clear_runtime_checkpoint(session)
        self.sessions.save(session)
        self._schedule_background(
            self.consolidator.maybe_consolidate_by_tokens(
                session,
                replay_max_messages=self._max_messages,
            )
        )
        content = final_content or "Background task completed."
        outbound_metadata: dict[str, Any] = {}
        if channel == "slack" and key.startswith("slack:") and key.count(":") >= 2:
            outbound_metadata["slack"] = {"thread_ts": key.split(":", 2)[2]}
        if origin_message_id := msg.metadata.get("origin_message_id"):
            outbound_metadata["origin_message_id"] = origin_message_id
        return OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content,
            metadata=outbound_metadata,
        )

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[..., Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
        pending_queue: asyncio.Queue | None = None,
        *,
        ephemeral_session: bool = False,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        self._refresh_provider_snapshot()

        if msg.channel == "system":
<<<<<<< HEAD
            channel, chat_id = (
                msg.chat_id.split(":", 1) if ":" in msg.chat_id else ("cli", msg.chat_id)
            )
            logger.info("Processing system message from {}", msg.sender_id)

            thread_id = msg.metadata.get("message_thread_id")
            # Honor session_key_override so subagent announces from threaded
            # callers route to the originating thread session.
            sk_override = getattr(msg, "session_key_override", None)
            if isinstance(sk_override, str) and sk_override:
                key = sk_override
            elif thread_id is not None:
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
                metadata=msg.metadata,
                session_key=key,
            )
            _hist_kwargs: dict[str, Any] = {
                "max_messages": self._max_messages,
                "max_tokens": self._replay_token_budget(),
                "include_timestamps": True,
            }
            history = session.get_history(**_hist_kwargs)
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
                metadata=msg.metadata,
                session_key=key,
                model_override=self._model_overrides.get(key),
                temperature_override=self._temperature_overrides.get(key),
                on_turn_saved=_on_turn_saved_sys,
                pending_queue=pending_queue,
            )
            if len(run_result) >= 5:
                final_content, _, all_msgs, stop_reason, _ = run_result[:5]
            elif len(run_result) >= 3:
                final_content, _, all_msgs = run_result[:3]
                stop_reason = "stop"
            else:
                raise ValueError("_run_agent_loop returned unexpected result shape")
            if final_content:
                final_content = self._strip_message_time_prefix(final_content)
                if stop_reason != "error" and all_msgs and all_msgs[-1].get("role") == "assistant":
                    all_msgs[-1] = {**all_msgs[-1], "content": final_content}
            self._save_turn(session, all_msgs, 1 + len(history))
            self._clear_pending_user_turn(session)
            session.enforce_file_cap(on_archive=self.context.memory.raw_archive)
            self._clear_runtime_checkpoint(session)
            self.sessions.save(session)
            self._schedule_background(self.consolidator.maybe_consolidate_by_tokens(session))
            is_cron = msg.channel == "cron"
            metadata = dict(msg.metadata or {})
            if thread_id is not None:
                metadata["message_thread_id"] = thread_id
            options = ask_user_options_from_messages(all_msgs) if stop_reason == "ask_user" else []
            content, buttons = ask_user_outbound(
                format_provider_error(final_content, is_cron=is_cron)
                or "Background task completed.",
                options,
                channel,
            )
            # Reconstruct channel-specific metadata from session.key so the
            # outbound reply lands in the originating thread (not the channel
            # top-level). The announce InboundMessage carries only
            # injected_event metadata; we recover thread_ts from the session
            # key, which slack writes as "slack:<chat_id>:<thread_ts>".
            outbound_metadata: dict[str, Any] = {}
            if channel == "slack" and key.startswith("slack:") and key.count(":") >= 2:
                outbound_metadata["slack"] = {"thread_ts": key.split(":", 2)[2]}
            return OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=content,
                buttons=buttons,
                metadata={**metadata, **outbound_metadata},
=======
            return await self._process_system_message(
                msg,
                session_key=session_key,
                on_progress=on_progress,
                on_stream=on_stream,
                on_stream_end=on_stream_end,
                pending_queue=pending_queue,
            )

        key = session_key or msg.session_key
        t0 = time.time()
        ctx = TurnContext(
            msg=msg,
            session=None,
            session_key=key,
            state=TurnState.RESTORE,
            turn_id=f"{key}:{time.time_ns()}",
            turn_wall_started_at=t0,
            visible_run_started_at=turn_continuation.internal_continuation_run_started_at(
                msg.metadata,
            ),
            on_progress=on_progress,
            on_stream=on_stream,
            on_stream_end=on_stream_end,
            pending_queue=pending_queue,
        )

        while ctx.state is not TurnState.DONE:
            handler_name = f"_state_{ctx.state.name.lower()}"
            handler = getattr(self, handler_name, None)
            if handler is None:
                raise RuntimeError(f"Missing state handler for {ctx.state}")

            t0 = time.perf_counter()
            try:
                event = await handler(ctx)
            except Exception:
                duration = (time.perf_counter() - t0) * 1000
                ctx.trace.append(
                    StateTraceEntry(
                        state=ctx.state,
                        started_at=t0,
                        duration_ms=duration,
                        event="",
                        error="exception",
                    )
                )
                raise

            duration = (time.perf_counter() - t0) * 1000
            ctx.trace.append(
                StateTraceEntry(
                    state=ctx.state,
                    started_at=t0,
                    duration_ms=duration,
                    event=event,
                )
            )
            logger.debug(
                "[turn {}] State {} took {:.1f}ms -> event {}",
                ctx.turn_id,
                ctx.state.name,
                duration,
                event,
>>>>>>> origin/main
            )

            next_state = self._TRANSITIONS.get((ctx.state, event))
            if next_state is None:
                raise RuntimeError(
                    f"[turn {ctx.turn_id}] No transition from {ctx.state} "
                    f"on event {event!r}"
                )
            ctx.state = next_state

        logger.debug(
            "[turn {}] Turn completed after {} states",
            ctx.turn_id,
            len(ctx.trace),
        )
        return ctx.outbound

    def _assemble_outbound(
        self,
        msg: InboundMessage,
        final_content: str,
        all_msgs: list[dict[str, Any]],
        stop_reason: str,
        had_injections: bool,
        on_stream: Callable[[str], Awaitable[None]] | None,
        *,
        turn_latency_ms: int | None = None,
    ) -> OutboundMessage | None:
        """Assemble the final outbound message from turn results."""
        # MessageTool suppression
        if (mt := self.tools.get("message")) and isinstance(mt, MessageTool) and mt._sent_in_turn:
            if not had_injections or stop_reason == "empty_final_response":
                return None

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)

        meta = dict(msg.metadata or {})
        if on_stream is not None and stop_reason not in {"error", "tool_error"}:
            meta["_streamed"] = True
        if turn_latency_ms is not None:
            meta["latency_ms"] = int(turn_latency_ms)

        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            metadata=meta,
        )

    async def _state_restore(self, ctx: TurnContext) -> TurnState:
        """Restore checkpoint / pending user turn; extract documents."""
        msg = ctx.msg

        if msg.media:
<<<<<<< HEAD
            new_content, image_only = extract_documents(msg.content, msg.media)
            if dataclasses.is_dataclass(msg):
                msg = dataclasses.replace(msg, content=new_content, media=image_only)
            else:
                msg.content = new_content
                msg.media = image_only
=======
            new_content, image_only = self._prepare_message_media(msg.content, msg.media)
            ctx.msg = dataclasses.replace(msg, content=new_content, media=image_only)
            msg = ctx.msg
>>>>>>> origin/main

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

<<<<<<< HEAD
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
=======
        # Session is already fetched by the caller (_process_message) but
        # ensure it exists in case this handler is invoked independently.
        if ctx.session is None:
            ctx.session = self.sessions.get_or_create(ctx.session_key)
        await self._runtime_events().session_turn_started(msg, ctx.session_key)
        self.workspace_scopes.persist_message_scope(ctx.session, msg)

        if self._restore_runtime_checkpoint(ctx.session):
            self.sessions.save(ctx.session)
        if self._restore_pending_user_turn(ctx.session):
            self.sessions.save(ctx.session)

        return "ok"

    def _prepare_message_media(self, content: str, media: list[str]) -> tuple[str, list[str]]:
        if self._should_extract_document_text():
            return extract_documents(content, media)
        return reference_non_image_attachments(content, media)

    def _should_extract_document_text(self) -> bool:
        if self.channels_config is None:
            return True
        return self.channels_config.extract_document_text

    async def _state_compact(self, ctx: TurnContext) -> str:
        ctx.session, pending = self.auto_compact.prepare_session(ctx.session, ctx.session_key)
        ctx.pending_summary = pending
        return "ok"

    async def _state_command(self, ctx: TurnContext) -> str:
        raw = ctx.msg.content.strip()
        cmd_ctx = CommandContext(
            msg=ctx.msg, session=ctx.session, key=ctx.session_key, raw=raw, loop=self
        )
        result = await self.commands.dispatch(cmd_ctx)
        if result is not None:
            ctx.outbound = result
            # Shortcut commands skip BUILD and SAVE, so we must persist the
            # turn here so WebUI history hydration after _turn_end sees the
            # message.  Mark messages with _command so get_history can filter
            # them out of LLM context.  /new is excluded because it
            # intentionally clears the session.
            if raw.lower() != "/new":
                ctx.user_persisted_early = self._persist_user_message_early(
                    ctx.msg, ctx.session, _command=True
                )
                ctx.session.add_message(
                    "assistant", result.content, _command=True
                )
                self.sessions.save(ctx.session)
                self._clear_pending_user_turn(ctx.session)
            return "shortcut"
        return "dispatch"
>>>>>>> origin/main

    async def _state_build(self, ctx: TurnContext) -> str:
        await self.consolidator.maybe_consolidate_by_tokens(
            ctx.session,
            replay_max_messages=self._max_messages,
        )
        self._set_tool_context(
<<<<<<< HEAD
            msg.channel,
            msg.chat_id,
            msg.metadata.get("message_id"),
            msg.metadata.get("message_thread_id"),
            metadata=msg.metadata,
            session_key=key,
=======
            ctx.msg.channel,
            ctx.msg.chat_id,
            ctx.msg.metadata.get("message_id"),
            ctx.msg.metadata,
            session_key=ctx.session_key,
>>>>>>> origin/main
        )
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        _hist_kwargs: dict[str, Any] = {
            "max_messages": self._max_messages,
            "max_tokens": self._replay_token_budget(),
            "include_timestamps": True,
        }
<<<<<<< HEAD
        history = session.get_history(**_hist_kwargs) if session else []

        pending_ask_id = pending_ask_user_id(history)
        if pending_ask_id:
            initial_messages = ask_user_tool_result_messages(
                self.context.build_system_prompt(channel=msg.channel),
                history,
                pending_ask_id,
                msg.content,
            )
        else:
            initial_messages = self.context.build_messages(
                history=history,
                current_message=msg.content,
                session_summary=pending,
                media=msg.media if msg.media else None,
                channel=msg.channel,
                chat_id=self._runtime_chat_id(msg),
                thread_id=msg.metadata.get("message_thread_id"),
            )

        async def _bus_progress(
            content: str,
            *,
            tool_hint: bool = False,
            tool_events: list[dict[str, Any]] | None = None,
        ) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            meta["_tool_hint"] = tool_hint
            if tool_events:
                meta["_tool_events"] = tool_events
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

        # Persist the triggering user message up front so a mid-turn crash
        # doesn't silently lose the prompt on recovery. ``media`` rides along
        # as raw on-disk paths — sanitized image blocks are stripped from
        # JSONL, and webui replay needs the paths to mint signed URLs.
        user_persisted_early = False
        media_paths = [p for p in (msg.media or []) if isinstance(p, str) and p]
        has_text = isinstance(msg.content, str) and msg.content.strip()
        if session is not None and not pending_ask_id and (has_text or media_paths):
            extra: dict[str, Any] = {"media": list(media_paths)} if media_paths else {}
            text = msg.content if isinstance(msg.content, str) else ""
            session.add_message("user", text, **extra)
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
            metadata=msg.metadata,
            session_key=key,
            model_override=self._model_overrides.get(key),
            temperature_override=self._temperature_overrides.get(key),
            pending_queue=pending_queue,
        )

        if final_content is None or not final_content.strip():
            final_content = EMPTY_FINAL_RESPONSE_MESSAGE
        else:
            final_content = self._strip_message_time_prefix(final_content)
            if stop_reason != "error" and all_msgs and all_msgs[-1].get("role") == "assistant":
                all_msgs[-1] = {**all_msgs[-1], "content": final_content}

        # Skip the already-persisted user message when saving the turn
        save_skip = 1 + len(history) + (1 if user_persisted_early else 0)
        if session is not None:
            self._save_turn(session, all_msgs, save_skip)
            session.enforce_file_cap(on_archive=self.context.memory.raw_archive)
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
        final_content, buttons = ask_user_outbound(
            final_content,
            ask_user_options_from_messages(all_msgs) if stop_reason == "ask_user" else [],
            msg.channel,
        )
        if on_stream is not None and stop_reason == "completed":
            meta["_streamed"] = True
            if is_provider_error_message(final_content):
                meta["_streamed_error"] = True
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=format_provider_error(final_content),
            metadata=meta,
            buttons=buttons,
=======
        ctx.history = ctx.session.get_history(**_hist_kwargs)
        self._runtime_events().record_turn_runtime(
            ctx.session_key,
            self.llm_runtime(),
        )

        ctx.initial_messages = self._build_initial_messages(
            ctx.msg,
            ctx.session,
            ctx.history,
            ctx.pending_summary,
        )
        ctx.user_persisted_early = self._persist_user_message_early(
            ctx.msg, ctx.session
>>>>>>> origin/main
        )

        if ctx.on_progress is None:
            ctx.on_progress = await self._build_bus_progress_callback(ctx.msg)
        if ctx.on_retry_wait is None:
            ctx.on_retry_wait = await self._build_retry_wait_callback(ctx.msg)

        return "ok"

    async def _state_run(self, ctx: TurnContext) -> str:
        if ctx.visible_run_started_at is None:
            ctx.visible_run_started_at = time.time()
        await self._runtime_events().run_status_changed(
            ctx.msg,
            ctx.session_key,
            "running",
            started_at=ctx.visible_run_started_at,
        )
        result = await self._run_agent_loop(
            ctx.initial_messages,
            on_progress=ctx.on_progress,
            on_stream=ctx.on_stream,
            on_stream_end=ctx.on_stream_end,
            on_retry_wait=ctx.on_retry_wait,
            session=ctx.session,
            channel=ctx.msg.channel,
            chat_id=ctx.msg.chat_id,
            message_id=ctx.msg.metadata.get("message_id"),
            metadata=ctx.msg.metadata,
            session_key=ctx.session_key,
            pending_queue=ctx.pending_queue,
        )
        final_content, tools_used, all_msgs, stop_reason, had_injections = result
        ctx.final_content = final_content
        ctx.tools_used = tools_used
        ctx.all_messages = all_msgs
        ctx.stop_reason = stop_reason
        ctx.had_injections = had_injections
        await turn_continuation.maybe_continue_turn(ctx)
        return "ok"

    async def _state_save(self, ctx: TurnContext) -> str:
        turn_continuation.prepare_save_boundary(ctx)

        if (
            (ctx.final_content is None or not ctx.final_content.strip())
            and not ctx.suppress_response
        ):
            ctx.final_content = EMPTY_FINAL_RESPONSE_MESSAGE

        latency_started_at = (
            ctx.visible_run_started_at
            if turn_continuation.internal_continuation_inbound(ctx.msg.metadata)
            and ctx.visible_run_started_at is not None
            else ctx.turn_wall_started_at
        )
        ctx.turn_latency_ms = max(0, int((time.time() - latency_started_at) * 1000))
        self._save_turn(
            ctx.session, ctx.all_messages, ctx.save_skip,
            turn_latency_ms=ctx.turn_latency_ms,
        )
        self._runtime_events().record_turn_latency(
            ctx.session_key,
            ctx.turn_latency_ms,
        )
        ctx.session.enforce_file_cap(on_archive=self.context.memory.raw_archive)
        self._clear_pending_user_turn(ctx.session)
        self._clear_runtime_checkpoint(ctx.session)
        self.sessions.save(ctx.session)
        self._schedule_background(
            self.consolidator.maybe_consolidate_by_tokens(
                ctx.session,
                replay_max_messages=self._max_messages,
            )
        )
        return "ok"

    async def _state_respond(self, ctx: TurnContext) -> str:
        if ctx.suppress_response:
            ctx.outbound = None
            return "ok"
        ctx.outbound = self._assemble_outbound(
            ctx.msg,
            ctx.final_content,
            ctx.all_messages,
            ctx.stop_reason,
            ctx.had_injections,
            ctx.on_stream,
            turn_latency_ms=ctx.turn_latency_ms,
        )
        return "ok"

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

    def _save_turn(
        self,
        session: Session,
        messages: list[dict],
        skip: int,
        *,
        turn_latency_ms: int | None = None,
    ) -> None:
        """Save new-turn messages into session, truncating large tool results."""
        from datetime import datetime

        last_assistant_idx: int | None = None
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
<<<<<<< HEAD
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
=======
                if isinstance(content, str) and ContextBuilder._RUNTIME_CONTEXT_TAG in content:
                    # Strip the runtime-context block appended at the end.
                    tag_pos = content.find(ContextBuilder._RUNTIME_CONTEXT_TAG)
                    before = content[:tag_pos].rstrip("\n ")
                    if before:
                        entry["content"] = before
                    else:
                        continue
>>>>>>> origin/main
                if isinstance(content, list):
                    filtered = self._sanitize_persisted_blocks(content, drop_runtime=True)
                    if not filtered:
                        continue
                    entry["content"] = filtered
            entry.setdefault("timestamp", datetime.now().isoformat())
            session.messages.append(entry)
            if role == "assistant":
                last_assistant_idx = len(session.messages) - 1
        if turn_latency_ms is not None and last_assistant_idx is not None:
            session.messages[last_assistant_idx]["latency_ms"] = int(turn_latency_ms)
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
        on_progress: Callable[..., Awaitable[None]] | None = None,
        on_stream: Callable[[str], Awaitable[None]] | None = None,
        on_stream_end: Callable[..., Awaitable[None]] | None = None,
        thread_id: int | None = None,
        ephemeral_session: bool = False,
    ) -> OutboundMessage | None:
        """Process a message directly and return the outbound payload."""
        await self._connect_mcp()
        metadata = {"message_thread_id": thread_id} if thread_id is not None else {}
        msg = InboundMessage(
<<<<<<< HEAD
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
=======
            channel=channel, sender_id="user", chat_id=chat_id,
            content=content, media=media or [],
        )
        # Share the dispatch lock so direct calls serialize with bus turns.
        lock = self._session_locks.setdefault(session_key, asyncio.Lock())
        try:
            async with lock:
                return await self._process_message(
                    msg,
                    session_key=session_key,
                    on_progress=on_progress,
                    on_stream=on_stream,
                    on_stream_end=on_stream_end,
                )
        finally:
            await self._runtime_events().run_status_changed(msg, session_key, "idle")
            self._runtime_events().clear_turn(session_key)
>>>>>>> origin/main
