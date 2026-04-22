"""Spawn tool for creating background subagents."""

from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


class SpawnTool(Tool):
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

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
                "subagent_id": {
                    "type": "string",
                    "description": "Optional configured subagent profile to use for this task",
                },
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        label: str | None = None,
        subagent_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent to execute the given task."""
        spawn_kwargs: dict[str, Any] = {
            "task": task,
            "label": label,
            "origin_channel": self._origin_channel.get(),
            "origin_chat_id": self._origin_chat_id.get(),
            "origin_thread_id": self._origin_thread_id.get(),
            "session_key": self._session_key.get(),
            "subagent_id": subagent_id,
            "model_override": self._model_override.get(),
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
            )
