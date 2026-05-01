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
        self._overrides: dict[str, dict[str, Any]] = {}
        self.cumulative_usage: dict[str, int] = {}

    def set_provider(self, provider: "LLMProvider") -> None:
        self._provider = provider

    def set_runner(self, runner: Any) -> None:
        self._runner = runner

    def set_tool_factories(self, factories: dict[str, Any]) -> None:
        self._tool_factories = factories

    def set_subagent_overrides(self, overrides: dict[str, dict[str, Any]]) -> None:
        self._overrides = overrides

    @property
    def name(self) -> str:
        return "delegate"

    @property
    def description(self) -> str:
        agents = self._loader.list_all()
        names = ", ".join(f"{a.name} ({a.description})" for a in agents)
        return (
            "Run a specialized sub-agent defined in agents/*.md files. "
            "No config setup needed — just the .md file in the agents directory. "
            "Each sub-agent has its own model and isolated tool set. "
            "PREFER this over spawn for agent-file-based tasks. "
            f"Available agents: {names or 'none (create agents/*.md to add)'}"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        agents = self._loader.list_all()
        names = [a.name for a in agents]

        # Build per-agent description with tools + model so the model
        # doesn't need glob/read_file to discover agent capabilities.
        agent_desc_parts: list[str] = []
        for a in agents:
            tools_str = ", ".join(a.tools) if a.tools else "no tools"
            agent_desc_parts.append(
                f"{a.name} [{a.model or 'default model'}, tools: {tools_str}] — {a.description}"
            )
        agent_desc = " ".join(agent_desc_parts) if agent_desc_parts else "none (create agents/*.md to add)"

        props: dict[str, Any] = {
            "agent": {
                "type": "string",
                "description": f"Sub-agent to run: {agent_desc}",
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
        overrides = getattr(self, "_overrides", {}).get(agent)
        config = self._loader.load(agent, overrides=overrides)
        if config is None:
            return json.dumps({"success": False, "error": f"Agent '{agent}' not found."})

        if self._runner is None or self._provider is None:
            return json.dumps({
                "success": False,
                "error": f"Agent '{agent}' runner not initialized. Delegate unavailable."
            })

        logger.info("delegate agent=%s model=%s task=%.80s", agent, config.model, task)
        try:
            result = await self._run_subagent(config, task)
            logger.info("delegate agent=%s completed", agent)
            return json.dumps({"success": True, "agent": agent, "result": result})
        except Exception as e:
            logger.exception("delegate agent=%s failed", agent)
            return json.dumps({"success": False, "agent": agent, "error": str(e)})

    async def _run_subagent(self, config: AgentConfig, task: str) -> str:
        from nanobot.agent.tools.registry import ToolRegistry
        from nanobot.agent.runner import AgentRunner, AgentRunSpec

        tools = ToolRegistry()
        for tool_name in config.tools:
            factory = self._tool_factories.get(tool_name)
            if factory:
                tools.register(factory())

        models_to_try = [config.model] + config.fallback_models
        last_error: Exception | None = None

        if len(models_to_try) > 1:
            logger.debug("delegate fallback chain: %s", models_to_try)

        for idx, model in enumerate(models_to_try):
            if idx > 0:
                logger.info("delegate falling back to model=%s (attempt %d/%d)", model, idx + 1, len(models_to_try))

        for model in models_to_try:
            spec = AgentRunSpec(
                initial_messages=[
                    {"role": "system", "content": config.system_prompt},
                    {"role": "user", "content": task},
                ],
                tools=tools,
                model=model,
                max_iterations=config.max_iterations,
                max_tool_result_chars=16_000,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
            )

            try:
                runner = AgentRunner(self._provider)
                result = await runner.run(spec)
                # Log token usage for visibility
                u = result.usage or {}
                logger.info(
                    "delegate model=%s stop=%s tokens_in=%d tokens_out=%d cached=%d iters=%d",
                    model,
                    result.stop_reason,
                    u.get("prompt_tokens", 0),
                    u.get("completion_tokens", 0),
                    u.get("cached_tokens", 0),
                    len(result.tool_events or []),
                )
                # Accumulate sub-agent token usage for stats visibility
                if result.usage:
                    for k, v in result.usage.items():
                        self.cumulative_usage[k] = self.cumulative_usage.get(k, 0) + v
                if result.stop_reason != "error" or model == models_to_try[-1]:
                    return result.final_content or "(no output)"
                last_error = Exception(result.error or "sub-agent returned error")
            except Exception as e:
                last_error = e
                if model == models_to_try[-1]:
                    raise

        raise last_error or RuntimeError("sub-agent failed")

    def execute_sync(self, agent: str, task: str) -> str:
        """Synchronous fallback for tests."""
        config = self._loader.load(agent)
        if config is None:
            return f"Error: agent '{agent}' not found"
        return f"Would delegate to {agent}: {task[:50]}..."
