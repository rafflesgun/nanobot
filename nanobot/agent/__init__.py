"""Agent core module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nanobot.agent.context import ContextBuilder
from nanobot.agent.hook import (
    AgentHook,
    AgentHookContext,
    AgentRunHookContext,
    AgentTurnHookContext,
    AgentTurnHookFactory,
    CompositeHook,
)
from nanobot.agent.memory import MemoryStore
from nanobot.agent.skills import SkillsLoader
from nanobot.agent.subagent import SubagentManager

__all__ = [
    "AgentHook",
    "AgentHookContext",
    "AgentRunHookContext",
    "AgentTurnHookContext",
    "AgentTurnHookFactory",
    "AgentLoop",
    "CompositeHook",
    "ContextBuilder",
    "MemoryStore",
    "SkillsLoader",
    "SubagentManager",
]


if TYPE_CHECKING:
    from nanobot.agent.loop import AgentLoop


def __getattr__(name: str):
    if name == "AgentLoop":
        from nanobot.agent.loop import AgentLoop

        return AgentLoop
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
