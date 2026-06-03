"""Subagent manager for background task execution."""

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from loguru import logger
from nanobot.utils.prompt_templates import render_template

from nanobot.agent.hook import AgentHook, AgentHookContext
<<<<<<< HEAD
from nanobot.agent.skills import BUILTIN_SKILLS_DIR
from nanobot.agent.runner import AgentRunSpec, AgentRunner
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
=======
from nanobot.agent.runner import AgentRunner, AgentRunSpec
from nanobot.agent.tools.context import ToolContext
from nanobot.agent.tools.file_state import FileStates
from nanobot.agent.tools.loader import ToolLoader
>>>>>>> origin/main
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.security.workspace_access import (
    WorkspaceScope,
    bind_workspace_scope,
    reset_workspace_scope,
    workspace_sandbox_status,
)
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import AgentDefaults, ToolsConfig
from nanobot.providers.base import LLMProvider
from nanobot.utils.stats import StatsManager


@dataclass(slots=True)
class SubagentStatus:
    """Real-time status of a running subagent."""

    task_id: str
    label: str
    task_description: str
    started_at: float
    phase: str = "initializing"
    iteration: int = 0
    tool_events: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    stop_reason: str | None = None
    error: str | None = None


class _SubagentHook(AgentHook):
    """Hook for subagent execution — logs tool calls and updates status."""

    def __init__(self, task_id: str, status: SubagentStatus | None = None) -> None:
        super().__init__()
        self._task_id = task_id
        self._status = status

    async def before_execute_tools(self, context: AgentHookContext) -> None:
        for tool_call in context.tool_calls:
            args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
            logger.debug(
                "Subagent [{}] executing: {} with arguments: {}",
                self._task_id,
                tool_call.name,
                args_str,
            )

    async def after_iteration(self, context: AgentHookContext) -> None:
        if self._status is None:
            return
        self._status.iteration = context.iteration
        self._status.tool_events = list(context.tool_events)
        self._status.usage = dict(context.usage)
        if context.error:
            self._status.error = str(context.error)


class SubagentManager:
    """Manages background subagent execution."""

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
<<<<<<< HEAD
        max_tool_result_chars: int | None = None,
        fallback_model: str | None = None,
        fallback_models: list[str] | None = None,
        agents_config: "AgentsConfig | None" = None,
        provider_factory: Callable[["AgentDefaults"], LLMProvider] | None = None,
        web_search_config: "WebSearchConfig | None" = None,
        web_proxy: str | None = None,
        web_config: Any | None = None,
        exec_config: "ExecToolConfig | None" = None,
=======
        tools_config: ToolsConfig | None = None,
>>>>>>> origin/main
        restrict_to_workspace: bool = False,
        extra_read: list[str] | None = None,
        extra_write: list[str] | None = None,
        disabled_skills: list[str] | None = None,
        max_iterations: int | None = None,
        max_concurrent_subagents: int | None = None,
        llm_wall_timeout_for_session: Callable[[str | None], float | None] | None = None,
    ):
<<<<<<< HEAD
        from nanobot.config.schema import (
            AgentsConfig,
            ExecToolConfig,
            WebSearchConfig,
            WebToolsConfig,
        )

=======
        defaults = AgentDefaults()
>>>>>>> origin/main
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
<<<<<<< HEAD
        self.max_tool_result_chars = (
            max_tool_result_chars if max_tool_result_chars is not None else 16000
        )
        self.fallback_model = fallback_model
        self.fallback_models = fallback_models or []
        self.agents_config = agents_config or AgentsConfig()
        self.provider_factory = provider_factory
        if web_config is not None:
            self.web_config = web_config
        else:
            self.web_config = WebToolsConfig(
                enable=web_search_config is not None or web_proxy is not None,
                proxy=web_proxy,
                search=web_search_config or WebSearchConfig(),
            )
        self.exec_config = exec_config or ExecToolConfig()
=======
        self.tools_config = tools_config or ToolsConfig()
        self.max_tool_result_chars = max_tool_result_chars
>>>>>>> origin/main
        self.restrict_to_workspace = restrict_to_workspace
        self.extra_read = extra_read or []
        self.extra_write = extra_write or []
        self.disabled_skills = set(disabled_skills or [])
        self.max_iterations = (
            max_iterations
            if max_iterations is not None
            else defaults.max_tool_iterations
        )
        self.max_concurrent_subagents = (
            max_concurrent_subagents
            if max_concurrent_subagents is not None
            else defaults.max_concurrent_subagents
        )
<<<<<<< HEAD
=======
        self.runner = AgentRunner(provider)
        self._llm_wall_timeout_for_session = llm_wall_timeout_for_session
>>>>>>> origin/main
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._task_statuses: dict[str, SubagentStatus] = {}
        self._session_tasks: dict[str, set[str]] = {}  # session_key -> {task_id, ...}
        self.stats_manager = StatsManager(workspace)
        self.runner = AgentRunner(provider)

    def _subagent_tools_config(self) -> ToolsConfig:
        """Build a ToolsConfig scoped for subagent use."""
        return ToolsConfig(
            exec=self.tools_config.exec,
            web=self.tools_config.web,
            restrict_to_workspace=self.restrict_to_workspace,
        )

    def _build_tools(
        self,
        workspace: Path | None = None,
        tools_config: ToolsConfig | None = None,
    ) -> ToolRegistry:
        """Build an isolated subagent tool registry via ToolLoader."""
        root = self.workspace if workspace is None else workspace
        registry = ToolRegistry()
        cfg = tools_config if tools_config is not None else self._subagent_tools_config()
        ctx = ToolContext(
            config=cfg,
            workspace=str(root.resolve()),
            file_state_store=FileStates(),
            workspace_sandbox=workspace_sandbox_status(
                restrict_to_workspace=cfg.restrict_to_workspace,
                workspace=root,
            ),
        )
        ToolLoader().load(ctx, registry, scope="subagent")
        return registry

    def set_provider(self, provider: LLMProvider, model: str) -> None:
        self.provider = provider
        self.model = model
        self.runner.provider = provider

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        session_key: str | None = None,
<<<<<<< HEAD
        subagent_id: str | None = None,
        origin_thread_id: int | None = None,
        model_override: str | None = None,
=======
        origin_message_id: str | None = None,
        temperature: float | None = None,
        workspace_scope: WorkspaceScope | None = None,
>>>>>>> origin/main
    ) -> str:
        """Spawn a subagent to execute a task in the background."""
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
            "session_key": session_key,
            "thread_id": origin_thread_id,
        }

        status = SubagentStatus(
            task_id=task_id,
            label=display_label,
            task_description=task,
            started_at=time.monotonic(),
        )
        self._task_statuses[task_id] = status

        bg_task = asyncio.create_task(
            self._run_subagent(
                task_id,
                task,
                display_label,
                origin,
                status,
<<<<<<< HEAD
                subagent_id=subagent_id,
                model_override=model_override,
=======
                origin_message_id,
                temperature,
                workspace_scope,
>>>>>>> origin/main
            )
        )
        self._running_tasks[task_id] = bg_task
        if session_key:
            self._session_tasks.setdefault(session_key, set()).add(task_id)

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            self._task_statuses.pop(task_id, None)
            if session_key and (ids := self._session_tasks.get(session_key)):
                ids.discard(task_id)
                if not ids:
                    del self._session_tasks[session_key]

        bg_task.add_done_callback(_cleanup)

        logger.info("Spawned subagent [{}]: {}", task_id, display_label)
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."

    def list_profiles(self) -> list[dict[str, str]]:
        """Return configured non-default subagent profiles for tool advertising."""
        profiles: list[dict[str, str]] = []
        for agent_id in self.agents_config.agent_ids():
            if agent_id == "defaults":
                continue
            overrides = self.agents_config._agent_overrides(agent_id)
            profile = {"id": agent_id}
            if label := overrides.get("label"):
                profile["label"] = str(label)
            if description := overrides.get("description"):
                profile["description"] = str(description)
            elif model := overrides.get("model"):
                profile["description"] = f"model={model}"
            profiles.append(profile)
        return profiles

    def _resolve_subagent_backend(
        self, subagent_id: str | None
    ) -> tuple["AgentDefaults", LLMProvider]:
        """Resolve the agent config and provider for a subagent run."""
        agent_config = self.agents_config.resolve(subagent_id or "defaults")
        if self.provider_factory:
            return agent_config, self.provider_factory(agent_config)
        return agent_config, self.provider

    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
<<<<<<< HEAD
        status: SubagentStatus | None = None,
        subagent_id: str | None = None,
        model_override: str | None = None,
=======
        status: SubagentStatus,
        origin_message_id: str | None = None,
        temperature: float | None = None,
        workspace_scope: WorkspaceScope | None = None,
>>>>>>> origin/main
    ) -> None:
        """Execute the subagent task and announce the result."""
        status = status or SubagentStatus(
            task_id=task_id,
            label=label,
            task_description=task,
            started_at=time.monotonic(),
        )
        logger.info("Subagent [{}] starting task: {}", task_id, label)

        async def _on_checkpoint(payload: dict) -> None:
            status.phase = payload.get("phase", status.phase)
            status.iteration = payload.get("iteration", status.iteration)

        try:
<<<<<<< HEAD
            agent_config, provider = self._resolve_subagent_backend(subagent_id)

            # Build subagent tools (no message tool, no spawn tool)
            tools = ToolRegistry()
            allowed_dir: list[Path] = (
                (
                    [self.workspace]
                    + ([Path(p) for p in self.extra_write] if self.extra_write else [])
                )
                if self.restrict_to_workspace
                else None
            )
            extra_read: list[Path] = (
                (
                    [BUILTIN_SKILLS_DIR]
                    + ([Path(p) for p in self.extra_read] if self.extra_read else [])
                )
                if allowed_dir
                else None
            )
            tools.register(
                ReadFileTool(
                    workspace=self.workspace, allowed_dir=allowed_dir, extra_allowed_dirs=extra_read
                )
            )
            tools.register(WriteFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(EditFileTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(ListDirTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(
                ExecTool(
                    working_dir=str(self.workspace),
                    timeout=self.exec_config.timeout,
                    restrict_to_workspace=self.restrict_to_workspace,
                    allowed_dirs=allowed_dir,
                    sandbox=self.exec_config.sandbox,
                    path_append=self.exec_config.path_append,
                    allowed_env_keys=self.exec_config.allowed_env_keys,
                )
            )
            tools.register(GlobTool(workspace=self.workspace, allowed_dir=allowed_dir))
            tools.register(GrepTool(workspace=self.workspace, allowed_dir=allowed_dir))
            if self.web_config.enable:
                tools.register(
                    WebSearchTool(
                        config=self.web_config.search,
                        proxy=self.web_config.proxy,
                        user_agent=self.web_config.user_agent,
                    )
                )
                tools.register(
                    WebFetchTool(
                        config=self.web_config.fetch,
                        proxy=self.web_config.proxy,
                        user_agent=self.web_config.user_agent,
                    )
                )
            system_prompt = self._build_subagent_prompt()
=======
            root = workspace_scope.project_path if workspace_scope is not None else self.workspace
            cfg = None
            if workspace_scope is not None:
                cfg = self._subagent_tools_config()
                cfg.restrict_to_workspace = workspace_scope.restrict_to_workspace
            tools = self._build_tools(workspace=root, tools_config=cfg)
            system_prompt = self._build_subagent_prompt(workspace=root)
>>>>>>> origin/main
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]

<<<<<<< HEAD
            spec = AgentRunSpec(
                initial_messages=messages,
                tools=tools,
                model=model_override or agent_config.model,
                max_iterations=self.max_iterations,
                max_tool_result_chars=self.max_tool_result_chars,
                error_message="Subagent task failed.",
                concurrent_tools=False,
                workspace=self.workspace,
            )
            result = await self.runner.run(spec)
            final_result = result.final_content

            if final_result is None or (
                "maximum number of tool call iterations" in str(final_result)
            ):
                tool_events = getattr(result, "tool_events", [])

                def _field(event, key):
                    return event.get(key) if isinstance(event, dict) else getattr(event, key, None)

                completed = [e for e in tool_events if _field(e, "status") == "ok"]
                failed = [e for e in tool_events if _field(e, "status") == "error"]
                if failed:
                    lines = []
                    if completed:
                        lines.append("Completed steps:")
                        for e in completed:
                            lines.append(f"- {_field(e, 'name')}: {_field(e, 'detail')}")
                    if failed:
                        if lines:
                            lines.append("")
                        lines.append("Failure:")
                        for e in failed:
                            lines.append(f"- {_field(e, 'name')}: {_field(e, 'detail')}")
                    final_result = "\n".join(lines)
                else:
                    final_result = "Task completed but no final response was generated."

            status = "error" if ("Failure:" in str(final_result)) else "ok"
            logger.info("Subagent [{}] completed successfully", task_id)
            await self._announce_result(task_id, label, task, final_result, origin, status)

            # Record subagent token usage
            if hasattr(provider, "get_usage"):
                usage = provider.get_usage()
                if usage:
                    self.stats_manager.record_usage(
                        "system",
                        f"subagent:{task_id}",
                        agent_config.model,
                        usage.get("input_tokens", 0),
                        usage.get("output_tokens", 0),
                        usage.get("total_tokens", 0),
                        f"subagent:{task_id}",
                    )
=======
            sess_key = origin.get("session_key")
            llm_timeout = (
                self._llm_wall_timeout_for_session(sess_key)
                if self._llm_wall_timeout_for_session
                else None
            )
            token = bind_workspace_scope(workspace_scope) if workspace_scope is not None else None
            try:
                result = await self.runner.run(AgentRunSpec(
                    initial_messages=messages,
                    tools=tools,
                    model=self.model,
                    temperature=temperature,
                    max_iterations=self.max_iterations,
                    max_tool_result_chars=self.max_tool_result_chars,
                    hook=_SubagentHook(task_id, status),
                    max_iterations_message="Task completed but no final response was generated.",
                    error_message=None,
                    fail_on_tool_error=True,
                    checkpoint_callback=_on_checkpoint,
                    session_key=sess_key,
                    workspace=root,
                    llm_timeout_s=llm_timeout,
                ))
            finally:
                if token is not None:
                    reset_workspace_scope(token)
            status.phase = "done"
            status.stop_reason = result.stop_reason

            if result.stop_reason == "tool_error":
                status.tool_events = list(result.tool_events)
                await self._announce_result(
                    task_id, label, task,
                    self._format_partial_progress(result),
                    origin, "error", origin_message_id,
                )
            elif result.stop_reason == "error":
                await self._announce_result(
                    task_id, label, task,
                    result.error or "Error: subagent execution failed.",
                    origin, "error", origin_message_id,
                )
            else:
                final_result = result.final_content or "Task completed but no final response was generated."
                logger.info("Subagent [{}] completed successfully", task_id)
                await self._announce_result(task_id, label, task, final_result, origin, "ok", origin_message_id)
>>>>>>> origin/main

        except Exception as e:
            status.phase = "error"
            status.error = str(e)
            logger.exception("Subagent [{}] failed", task_id)
            await self._announce_result(task_id, label, task, f"Error: {e}", origin, "error", origin_message_id)

    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
        origin_message_id: str | None = None,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"

        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""

        # Inject as system message to trigger main agent.
        # Use session_key_override to align with the main agent's effective
        # session key (which accounts for unified sessions) so the result is
        # routed to the correct pending queue (mid-turn injection) instead of
        # being dispatched as a competing independent task.
        override = origin.get("session_key") or f"{origin['channel']}:{origin['chat_id']}"
        metadata: dict[str, Any] = {
            "injected_event": "subagent_result",
            "subagent_task_id": task_id,
        }
        if origin_message_id:
            metadata["origin_message_id"] = origin_message_id
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
            session_key_override=override,
<<<<<<< HEAD
            metadata={
                **(
                    {"message_thread_id": origin["thread_id"]}
                    if origin.get("thread_id") is not None
                    else {}
                ),
                "injected_event": "subagent_result",
                "subagent_task_id": task_id,
            },
=======
            metadata=metadata,
>>>>>>> origin/main
        )

        await self.bus.publish_inbound(msg)
        logger.debug(
            "Subagent [{}] announced result to {}:{}", task_id, origin["channel"], origin["chat_id"]
        )

    def _build_subagent_prompt(self, workspace: Path | None = None) -> str:
        """Build a focused system prompt for the subagent."""
        from nanobot.agent.context import ContextBuilder
        from nanobot.agent.skills import SkillsLoader

        time_ctx = ContextBuilder._build_runtime_context(None, None)
        root = workspace or self.workspace
        skills_summary = SkillsLoader(
            root,
            disabled_skills=self.disabled_skills,
        ).build_skills_summary()
        return render_template(
            "agent/subagent_system.md",
            time_ctx=time_ctx,
            workspace=str(root),
            skills_summary=skills_summary or "",
        )

    async def cancel_by_session(self, session_key: str) -> int:
        """Cancel all subagents for the given session. Returns count cancelled."""
        tasks = [
            self._running_tasks[tid]
            for tid in self._session_tasks.get(session_key, [])
            if tid in self._running_tasks and not self._running_tasks[tid].done()
        ]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)

    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)

    def get_running_count_by_session(self, session_key: str) -> int:
        """Return the number of currently running subagents for a session."""
        tids = self._session_tasks.get(session_key, set())
        return sum(
            1 for tid in tids if tid in self._running_tasks and not self._running_tasks[tid].done()
        )
