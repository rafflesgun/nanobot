"""Spawn tool for creating background subagents."""

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


class SpawnTool(Tool):
    """Tool to spawn a subagent for background task execution."""

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._session_key = "cli:direct"
        self._origin_thread_id: int | None = None
        self._model_override: str | None = None

    def set_context(
        self,
        channel: str,
        chat_id: str,
        model_override: str | None = None,
        thread_id: int | None = None,
    ) -> None:
        """Set the origin context for subagent announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._session_key = (
            f"{channel}:{chat_id}:topic:{thread_id}"
            if thread_id is not None
            else f"{channel}:{chat_id}"
        )
        self._origin_thread_id = thread_id
        self._model_override = model_override

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
        return await self._manager.spawn(
            task=task,
            label=label,
            origin_channel=self._origin_channel,
            origin_chat_id=self._origin_chat_id,
            origin_thread_id=self._origin_thread_id,
            session_key=self._session_key,
            subagent_id=subagent_id,
            model_override=self._model_override,
        )
