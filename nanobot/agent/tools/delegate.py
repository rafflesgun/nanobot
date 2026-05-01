"""Delegate tool — dispatches tasks to configured sub-agents."""
from __future__ import annotations

import json
import logging
from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool
from nanobot.agent.subagents import AgentLoader, AgentConfig

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class DelegateTool(Tool):
    def __init__(
        self,
        loader: AgentLoader,
        provider: "LLMProvider | None" = None,
        runner: Any = None,
    ) -> None:
        self._loader = loader
        self._provider = provider
        self._runner = runner
        self._tool_factories: dict[str, Any] = {}

    def set_provider(self, provider: "LLMProvider") -> None:
        self._provider = provider

    def set_runner(self, runner: Any) -> None:
        self._runner = runner

    def set_tool_factories(self, factories: dict[str, Any]) -> None:
        self._tool_factories = factories

    @property
    def name(self) -> str:
        return "delegate"

    @property
    def description(self) -> str:
        agents = self._loader.list_all()
        names = ", ".join(f"{a.name} ({a.description})" for a in agents)
        return (
            "Delegate a task to a specialized sub-agent with a focused tool set "
            f"and cheaper model. Available agents: {names or 'none'}"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        agents = self._loader.list_all()
        names = [a.name for a in agents]
        props: dict[str, Any] = {
            "agent": {
                "type": "string",
                "description": f"Sub-agent to delegate to: {', '.join(names)}",
            },
            "task": {
                "type": "string",
                "description": "Natural language task for the sub-agent to complete",
                "minLength": 1,
            },
        }
        if names:
            props["agent"]["enum"] = names
        return {
            "type": "object",
            "properties": props,
            "required": ["agent", "task"],
        }

    async def execute(self, agent: str, task: str, **_: Any) -> str:
        config = self._loader.load(agent)
        if config is None:
            return json.dumps({"success": False, "error": f"Agent '{agent}' not found."})

        if self._runner is None or self._provider is None:
            return json.dumps({
                "success": False,
                "error": f"Agent '{agent}' runner not initialized. Delegate unavailable."
            })

        try:
            result = await self._run_subagent(config, task)
            return json.dumps({"success": True, "agent": agent, "result": result})
        except Exception as e:
            logger.exception("Delegate to %s failed", agent)
            return json.dumps({"success": False, "agent": agent, "error": str(e)})

    async def _run_subagent(self, config: AgentConfig, task: str) -> str:
        from nanobot.agent.tools.registry import ToolRegistry
        from nanobot.agent.runner import AgentRunner, AgentRunSpec

        tools = ToolRegistry()
        for tool_name in config.tools:
            factory = self._tool_factories.get(tool_name)
            if factory:
                tools.register(factory())

        spec = AgentRunSpec(
            initial_messages=[
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": task},
            ],
            tools=tools,
            model=config.model,
            max_iterations=config.max_iterations,
            max_tool_result_chars=16_000,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
        )

        runner = AgentRunner(self._provider)
        result = await runner.run(spec)
        return result.final_content or "(no output)"

    def execute_sync(self, agent: str, task: str) -> str:
        """Synchronous fallback for tests."""
        config = self._loader.load(agent)
        if config is None:
            return f"Error: agent '{agent}' not found"
        return f"Would delegate to {agent}: {task[:50]}..."
