"""Spawn tool for creating background subagents."""

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool, tool_parameters
from nanobot.agent.tools.context import ContextAware, RequestContext
from nanobot.agent.tools.schema import NumberSchema, StringSchema, tool_parameters_schema

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


@tool_parameters(
    tool_parameters_schema(
        task=StringSchema("The task for the subagent to complete"),
        label=StringSchema("Optional short label for the task (for display)"),
        subagent_id=StringSchema(
            "ID of a configured subagent profile to use "
            "(e.g. research, writer).  Omit for a generic subagent."
        ),
        temperature=NumberSchema(
            description=(
                "Optional sampling temperature for the subagent "
                "(0.0 = deterministic, higher = more creative). "
                "Defaults to the provider's configured temperature."
            ),
            minimum=0.0,
            maximum=2.0,
        ),
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
        self._origin_thread_id: ContextVar[int | None] = ContextVar(
            "spawn_origin_thread_id", default=None
        )
        self._model_override: ContextVar[str | None] = ContextVar(
            "spawn_model_override", default=None
        )
        self._origin_message_id: ContextVar[str | None] = ContextVar(
            "spawn_origin_message_id",
            default=None,
        )

    def set_context(
        self,
        channel: str,
        chat_id: str,
        effective_key: str | None = None,
        model_override: str | None = None,
        thread_id: int | None = None,
    ) -> None:
        """Set the origin context for subagent announcements."""
        self._origin_channel.set(channel)
        self._origin_chat_id.set(chat_id)
        self._session_key.set(
            effective_key
            or (
                f"{channel}:{chat_id}:topic:{thread_id}"
                if thread_id is not None
                else f"{channel}:{chat_id}"
            )
        )
        self._origin_thread_id.set(thread_id)
        self._model_override.set(model_override)

    def set_origin_message_id(self, message_id: str | None) -> None:
        """Set the source message id for downstream deduplication."""
        self._origin_message_id.set(message_id)

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        description = (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done. "
            "For deliverables or existing projects, inspect the workspace first "
            "and use a dedicated subdirectory when helpful."
        )
        profiles = self._manager.list_profiles()
        if profiles:
            advertised = "; ".join(
                f"{profile['id']}: {profile.get('description') or profile.get('label') or 'configured profile'}"
                for profile in profiles
            )
            description += (
                f" Available configured subagents: {advertised}. Use subagent_id to select one."
            )
        return description

    async def execute(
        self,
        task: str,
        label: str | None = None,
        subagent_id: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent to execute the given task."""
        running_getter = getattr(self._manager, "get_running_count", None)
        limit = getattr(self._manager, "max_concurrent_subagents", None)
        if callable(running_getter) and isinstance(limit, int):
            running = running_getter()
            if running >= limit:
                return (
                    f"Cannot spawn subagent: concurrency limit reached "
                    f"({running}/{limit} running). Wait for a running subagent "
                    f"to complete before spawning a new one."
                )

        spawn_kwargs: dict[str, Any] = {
            "task": task,
            "label": label,
            "origin_channel": self._origin_channel.get(),
            "origin_chat_id": self._origin_chat_id.get(),
            "origin_thread_id": self._origin_thread_id.get(),
            "session_key": self._session_key.get(),
            "subagent_id": subagent_id,
            "model_override": self._model_override.get(),
            "origin_message_id": self._origin_message_id.get(),
            "temperature": temperature,
        }
        try:
            return await self._manager.spawn(**spawn_kwargs)
        except TypeError as exc:
            if "unexpected keyword argument" not in str(exc):
                raise
            return await self._manager.spawn(
                task=task,
                label=label,
                origin_channel=self._origin_channel.get(),
                origin_chat_id=self._origin_chat_id.get(),
                session_key=self._session_key.get(),
                origin_message_id=self._origin_message_id.get(),
                temperature=temperature,
            )
