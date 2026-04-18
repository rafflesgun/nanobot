"""Subagent manager for background task execution."""

import asyncio
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger
from nanobot.utils.prompt_templates import render_template

from nanobot.agent.hook import AgentHook, AgentHookContext
from nanobot.agent.skills import BUILTIN_SKILLS_DIR
from nanobot.agent.runner import AgentRunSpec, AgentRunner
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.search import GlobTool, GrepTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebFetchTool, WebSearchTool
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.config.schema import ExecToolConfig
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
        max_tool_result_chars: int | None = None,
        fallback_model: str | None = None,
        fallback_models: list[str] | None = None,
        agents_config: "AgentsConfig | None" = None,
        provider_factory: Callable[["AgentDefaults"], LLMProvider] | None = None,
        web_search_config: "WebSearchConfig | None" = None,
        web_proxy: str | None = None,
        web_config: Any | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
        extra_read: list[str] | None = None,
        extra_write: list[str] | None = None,
        disabled_skills: list[str] | None = None,
    ):
        from nanobot.config.schema import (
            AgentsConfig,
            ExecToolConfig,
            WebSearchConfig,
            WebToolsConfig,
        )

        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
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
        self.restrict_to_workspace = restrict_to_workspace
        self.extra_read = extra_read or []
        self.extra_write = extra_write or []
        self.disabled_skills = set(disabled_skills or [])
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._task_statuses: dict[str, SubagentStatus] = {}
        self._session_tasks: dict[str, set[str]] = {}  # session_key -> {task_id, ...}
        self.stats_manager = StatsManager(workspace)
        self.runner = AgentRunner(provider)

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        session_key: str | None = None,
        subagent_id: str | None = None,
        origin_thread_id: int | None = None,
        model_override: str | None = None,
    ) -> str:
        """Spawn a subagent to execute a task in the background."""
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
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
                subagent_id=subagent_id,
                model_override=model_override,
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
        status: SubagentStatus | None = None,
        subagent_id: str | None = None,
        model_override: str | None = None,
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
                    WebSearchTool(config=self.web_config.search, proxy=self.web_config.proxy)
                )
                tools.register(WebFetchTool(proxy=self.web_config.proxy))
            system_prompt = self._build_subagent_prompt()
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]

            spec = AgentRunSpec(
                initial_messages=messages,
                tools=tools,
                model=model_override or agent_config.model,
                max_iterations=15,
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

        except Exception as e:
            status.phase = "error"
            status.error = str(e)
            logger.error("Subagent [{}] failed: {}", task_id, e)
            await self._announce_result(task_id, label, task, f"Error: {e}", origin, "error")

    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"

        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""

        # Inject as system message to trigger main agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
            metadata=(
                {"message_thread_id": origin["thread_id"]}
                if origin.get("thread_id") is not None
                else {}
            ),
        )

        await self.bus.publish_inbound(msg)
        logger.debug(
            "Subagent [{}] announced result to {}:{}", task_id, origin["channel"], origin["chat_id"]
        )

    def _build_subagent_prompt(self) -> str:
        """Build a focused system prompt for the subagent."""
        from nanobot.agent.context import ContextBuilder
        from nanobot.agent.skills import SkillsLoader

        time_ctx = ContextBuilder._build_runtime_context(None, None)
        skills_summary = SkillsLoader(
            self.workspace,
            disabled_skills=self.disabled_skills,
        ).build_skills_summary()
        return render_template(
            "agent/subagent_system.md",
            time_ctx=time_ctx,
            workspace=str(self.workspace),
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
