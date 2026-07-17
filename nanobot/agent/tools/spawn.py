"""Spawn tool for creating background subagents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool, ToolResult, tool_parameters
from nanobot.agent.tools.context import current_request_context
from nanobot.agent.tools.schema import NumberSchema, StringSchema, tool_parameters_schema
from nanobot.security.workspace_access import current_workspace_scope

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


@tool_parameters(
    tool_parameters_schema(
        task=StringSchema("The task for the subagent to complete"),
        label=StringSchema("Optional short label for the task (for display)"),
        temperature=NumberSchema(
            description=(
                "Optional sampling temperature for the subagent "
                "(0.0 = deterministic, higher = more creative). "
                "Defaults to the provider's configured temperature."
            ),
            minimum=0.0,
            maximum=2.0,
        ),
        subagent_id=StringSchema("Optional configured subagent profile to use for this task"),
        required=["task"],
    )
)
class SpawnTool(Tool):
    """Tool to spawn a subagent for background task execution."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._compat_request_context = None

    @classmethod
    def create(cls, ctx: Any) -> Tool:
        return cls(manager=ctx.subagent_manager)

    def set_context(
        self,
        channel: str | Any,
        chat_id: str | None = None,
        *,
        thread_id: int | None = None,
        model_override: str | None = None,
    ) -> None:
        """Provide legacy direct callers with an explicit origin route."""
        from nanobot.agent.tools.context import RequestContext

        if not isinstance(channel, str):
            self._compat_request_context = channel
            return
        session_key = (
            f"{channel}:{chat_id}:topic:{thread_id}"
            if thread_id is not None
            else f"{channel}:{chat_id}"
        )
        self._compat_request_context = RequestContext(
            channel=channel,
            chat_id=chat_id or "direct",
            session_key=session_key,
            thread_id=thread_id,
            metadata={"_model_override": model_override} if model_override else {},
        )

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        desc = (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done. "
            "For deliverables or existing projects, inspect the workspace first "
            "and use a dedicated subdirectory when helpful."
        )
        with_profiles = getattr(self._manager, "list_profiles", None)
        profiles = with_profiles() if callable(with_profiles) else []
        if profiles:
            profile_text = "; ".join(
                f"{p.get('id')}: {p.get('description') or p.get('label') or ''}".strip()
                for p in profiles
                if p.get("id")
            )
            desc += f" Available configured subagents: {profile_text}. Use subagent_id to select one."
        return desc

    async def execute(
        self,
        task: str,
        label: str | None = None,
        temperature: float | None = None,
        subagent_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent to execute the given task."""
        running = self._manager.get_running_count()
        limit = self._manager.max_concurrent_subagents
        if isinstance(running, int) and isinstance(limit, int) and running >= limit:
            return (
                f"Cannot spawn subagent: concurrency limit reached "
                f"({running}/{limit} running). Wait for a running subagent "
                f"to complete before spawning a new one."
            )
        active_request_ctx = current_request_context()
        request_ctx = active_request_ctx or self._compat_request_context
        if request_ctx is None:
            return ToolResult.error("Error: spawn requires an active model runtime")
        origin_channel = request_ctx.channel
        origin_chat_id = request_ctx.chat_id
        session_key = request_ctx.session_key or f"{origin_channel}:{origin_chat_id}"
        call_kwargs: dict[str, Any] = {
            "task": task,
            "label": label,
            "origin_channel": origin_channel,
            "origin_chat_id": origin_chat_id,
            "origin_thread_id": request_ctx.thread_id,
            "session_key": session_key,
            "subagent_id": subagent_id,
            "model_override": request_ctx.metadata.get("_model_override"),
        }
        if active_request_ctx is not None:
            call_kwargs.update(
                origin_message_id=request_ctx.message_id,
                temperature=temperature,
                workspace_scope=current_workspace_scope(),
            )
            if request_ctx.runtime is not None:
                call_kwargs["runtime"] = request_ctx.runtime
        return await self._manager.spawn(
            **call_kwargs,
        )
