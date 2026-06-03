"""Tool for searching prior session transcripts."""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.session.search import SessionSearchService


class SessionSearchTool(Tool):
    def __init__(self, workspace: Any = None) -> None:
        self._service = SessionSearchService(workspace or Path.cwd())
        self._session_key: ContextVar[str | None] = ContextVar("session_search_key", default=None)

    def set_context(self, session_key: str | None = None, **_: Any) -> None:
        self._session_key.set(session_key)

    @property
    def name(self) -> str:
        return "session_search"

    @property
    def description(self) -> str:
        return "Search prior conversation sessions for related work and return compact excerpts."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to match against prior session transcripts",
                    "minLength": 1,
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of matching sessions to return",
                    "minimum": 1,
                    "maximum": 20,
                },
                "include_current_session": {
                    "type": "boolean",
                    "description": "Whether to include the active session in recall results",
                    "default": False,
                },
            },
            "required": ["query"],
        }

    @property
    def read_only(self) -> bool:
        return True

    async def execute(
        self,
        query: str,
        limit: int = 3,
        include_current_session: bool = False,
        **_: Any,
    ) -> str:
        if not query or not query.strip():
            return "Error: query cannot be empty"
        exclude = None if include_current_session else self._session_key.get()
        hits = self._service.search(query, limit=limit, exclude_session_key=exclude)
        if not hits:
            return f'No prior session matches found for "{query}".'

        lines = [f'## Session recall for "{query}"', ""]
        for hit in hits:
            lines.append(f"- Session: `{hit.session_key}`")
            lines.append(f"  Score: {hit.score}")
            if hit.last_timestamp:
                lines.append(f"  Last activity: {hit.last_timestamp}")
            lines.append(f"  Excerpt: {hit.excerpt}")
            lines.append("")
        return "\n".join(lines).rstrip()
