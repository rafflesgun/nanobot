"""Tool for searching prior session transcripts via FTS5 SQLite."""
from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any

from nanobot.agent.tools.base import Tool
from nanobot.session.store import SessionStore

logger = logging.getLogger(__name__)


class SessionSearchTool(Tool):
    def __init__(self, store: SessionStore) -> None:
        self._store = store
        self._session_key: ContextVar[str | None] = ContextVar(
            "session_search_key", default=None
        )

    def set_context(self, session_key: str | None = None, **_: Any) -> None:
        self._session_key.set(session_key)

    @property
    def name(self) -> str:
        return "session_search"

    @property
    def description(self) -> str:
        return (
            "Search your long-term memory of past conversations. "
            "TWO MODES: (1) Recent sessions — call with no query to browse recent session titles/timestamps (zero LLM cost). "
            "(2) Keyword search — provide a query to search across all past sessions. "
            "USE THIS when the user references past work, asks 'what did we do about X', or mentions something familiar."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query. Omit to browse recent sessions (no LLM cost).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 3, max 5).",
                    "minimum": 1,
                    "maximum": 5,
                },
            },
            "required": [],
        }

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, query: str = "", limit: int = 3, **_: Any) -> str:
        limit = max(1, min(limit, 5))

        # Mode 1: Recent sessions browse (zero LLM cost)
        if not query or not query.strip():
            return self._recent_sessions(limit)

        # Mode 2: Keyword search
        return self._keyword_search(query.strip(), limit)

    def _recent_sessions(self, limit: int) -> str:
        sessions = self._store.list_sessions_rich(limit=limit + 10)
        current_key = self._session_key.get()
        results = []
        for s in sessions:
            sid = s.get("id", "")
            if current_key and sid == current_key:
                continue
            results.append({
                "session_id": sid,
                "title": s.get("title"),
                "source": s.get("source", ""),
                "started_at": s.get("started_at", ""),
                "message_count": s.get("message_count", 0),
            })
            if len(results) >= limit:
                break
        return json.dumps({
            "success": True,
            "mode": "recent",
            "results": results,
            "count": len(results),
        }, ensure_ascii=False)

    def _keyword_search(self, query: str, limit: int) -> str:
        raw = self._store.search_messages(query, limit=50)
        if not raw:
            return json.dumps({
                "success": True, "query": query,
                "results": [], "count": 0,
                "message": "No matching sessions found.",
            }, ensure_ascii=False)

        # Deduplicate by session_id, preserving order (first = best match)
        seen: set[str] = set()
        deduped = []
        for r in raw:
            sid = r["session_id"]
            if sid not in seen:
                seen.add(sid)
                deduped.append(r)
            if len(deduped) >= limit:
                break

        current_key = self._session_key.get()
        results = []
        for r in deduped:
            if current_key and r["session_id"] == current_key:
                continue
            msgs = self._store.get_messages_as_conversation(r["session_id"])
            conversation = "\n".join(
                f"[{m['role']}]: {m.get('content', '')}" for m in msgs
            )
            results.append({
                "session_id": r["session_id"],
                "when": r.get("session_started", ""),
                "source": r.get("source", "unknown"),
                "model": r.get("model"),
                "conversation": conversation[:5000],
                "match_count": len(msgs),
            })

        return json.dumps({
            "success": True,
            "query": query,
            "mode": "keyword",
            "results": results,
            "count": len(results),
        }, ensure_ascii=False)
