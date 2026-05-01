"""Sub-agent loader, config, and runner."""
from __future__ import annotations

import logging
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    name: str
    description: str
    system_prompt: str
    model: str = ""
    temperature: float = 0.0
    tools: list[str] = field(default_factory=list)
    max_iterations: int = 3
    max_tokens: int = 4096
    trigger: str = "on_demand"
    channel: str | None = None


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class AgentLoader:
    def __init__(self, workspace_agents_dir: Path, builtin_dir: Path | None = None) -> None:
        self._workspace = workspace_agents_dir
        self._builtin = builtin_dir

    def load(self, name: str, overrides: dict[str, Any] | None = None) -> AgentConfig | None:
        content = self._read_agent_file(name)
        if content is None:
            return None
        config = self._parse(content)
        if overrides:
            for key in ("model", "temperature", "tools", "max_iterations", "max_tokens"):
                if key in overrides:
                    setattr(config, key, overrides[key])
        return config

    def list_all(self) -> list[AgentConfig]:
        seen: set[str] = set()
        result: list[AgentConfig] = []

        for base in (self._workspace, self._builtin):
            if base is None or not base.exists():
                continue
            for path in sorted(base.glob("*.md")):
                name = path.stem
                if name in seen:
                    continue
                seen.add(name)
                config = self.load(name)
                if config:
                    result.append(config)
        return result

    def _read_agent_file(self, name: str) -> str | None:
        for base in (self._workspace, self._builtin):
            if base is None:
                continue
            path = base / f"{name}.md"
            if path.exists():
                return path.read_text(encoding="utf-8")
        return None

    @staticmethod
    def _parse(content: str) -> AgentConfig:
        frontmatter: dict[str, Any] = {}
        body = content
        m = _FRONTMATTER_RE.match(content)
        if m:
            try:
                frontmatter = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                pass
            body = content[m.end():].strip()

        return AgentConfig(
            name=frontmatter.get("name", "unknown"),
            description=frontmatter.get("description", ""),
            system_prompt=body,
            model=frontmatter.get("model", ""),
            temperature=float(frontmatter.get("temperature", 0.0)),
            tools=frontmatter.get("tools") or [],
            max_iterations=int(frontmatter.get("max_iterations", 3)),
            max_tokens=int(frontmatter.get("max_tokens", 4096)),
            trigger=frontmatter.get("trigger", "on_demand"),
            channel=frontmatter.get("channel"),
        )
