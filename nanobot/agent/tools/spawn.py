"""Spawn tool for creating background subagents."""

from __future__ import annotations

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.context import ContextAware, RequestContext
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
class SpawnTool(Tool, ContextAware):
    """Tool to spawn a subagent for background task execution."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._origin_channel: ContextVar[str] = ContextVar("spawn_origin_channel", default="cli")
        self._origin_chat_id: ContextVar[str] = ContextVar("spawn_origin_chat_id", default="direct")
        self._session_key: ContextVar[str] = ContextVar("spawn_session_key", default="cli:direct")
        self._origin_message_id: ContextVar[str | None] = ContextVar(
            "spawn_origin_message_id",
            default=None,
        )
        self._origin_thread_id: ContextVar[int | None] = ContextVar(
            "spawn_origin_thread_id",
            default=None,
        )
        self._model_override: ContextVar[str | None] = ContextVar(
            "spawn_model_override",
            default=None,
        )

    @classmethod
    def create(cls, ctx: Any) -> Tool:
        return cls(manager=ctx.subagent_manager)

    def set_context(
        self,
        ctx: RequestContext | str,
        chat_id: str | None = None,
        effective_key: str | None = None,
        model_override: str | None = None,
        thread_id: int | None = None,
    ) -> None:
        """Set the origin context for subagent announcements."""
        if isinstance(ctx, RequestContext):
            metadata = ctx.metadata or {}
            thread_id = ctx.thread_id or metadata.get("message_thread_id")
            model_override = metadata.get("_model_override")
            channel = ctx.channel
            chat = ctx.chat_id
            effective_key = ctx.session_key or (
                f"{channel}:{chat}:topic:{thread_id}" if thread_id is not None else f"{channel}:{chat}"
            )
            message_id = ctx.message_id
        else:
            channel = ctx
            chat = chat_id or "direct"
            effective_key = effective_key or (
                f"{channel}:{chat}:topic:{thread_id}" if thread_id is not None else f"{channel}:{chat}"
            )
            message_id = None
        self._origin_channel.set(channel)
        self._origin_chat_id.set(chat)
        self._session_key.set(effective_key)
        self._origin_message_id.set(message_id)
        self._origin_thread_id.set(thread_id)
        self._model_override.set(model_override)

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
        call_kwargs: dict[str, Any] = {
            "task": task,
            "label": label,
            "origin_channel": self._origin_channel.get(),
            "origin_chat_id": self._origin_chat_id.get(),
            "origin_thread_id": self._origin_thread_id.get(),
            "session_key": self._session_key.get(),
            "subagent_id": subagent_id,
            "model_override": self._model_override.get(),
        }
        if self._origin_message_id.get() is not None:
            call_kwargs["origin_message_id"] = self._origin_message_id.get()
        if temperature is not None:
            call_kwargs["temperature"] = temperature
        if current_workspace_scope() is not None:
            call_kwargs["workspace_scope"] = current_workspace_scope()
        return await self._manager.spawn(**call_kwargs)
