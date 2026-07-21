"""Search past session transcripts for related work."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SessionSearchHit:
    session_key: str
    path: Path
    score: int
    match_count: int
    excerpt: str
    first_timestamp: str | None
    last_timestamp: str | None


class SessionSearchService:
    """Small scan-based recall over workspace session JSONL files."""

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace
        self._sessions_dir = workspace / "sessions"

    def search(
        self,
        query: str,
        *,
        limit: int = 3,
        exclude_session_key: str | None = None,
        excerpt_chars: int = 600,
    ) -> list[SessionSearchHit]:
        terms = self._normalize_query(query)
        if not terms or limit <= 0 or not self._sessions_dir.exists():
            return []

        hits: list[SessionSearchHit] = []
        for path in sorted(self._sessions_dir.glob("*.jsonl")):
            hit = self._search_file(path, terms, excerpt_chars=excerpt_chars)
            if hit is not None:
                if exclude_session_key and hit.session_key == exclude_session_key:
                    continue
                hits.append(hit)

        hits.sort(key=lambda item: (-item.score, item.session_key))
        return hits[:limit]

    @staticmethod
    def _normalize_query(query: str) -> list[str]:
        return [term for term in re.findall(r"[a-z0-9_./:-]+", query.lower()) if term]

    @staticmethod
    def _session_key_from_path(path: Path) -> str:
        stem = path.stem
        return stem.replace("_", ":")

    def _search_file(
        self,
        path: Path,
        terms: list[str],
        *,
        excerpt_chars: int,
    ) -> SessionSearchHit | None:
        phrase = " ".join(terms)
        texts: list[str] = []
        first_timestamp: str | None = None
        last_timestamp: str | None = None
        match_count = 0
        score = 0
        session_key = self._session_key_from_path(path)

        try:
            with open(path, encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("_type") == "metadata":
                        metadata_key = row.get("key")
                        if isinstance(metadata_key, str) and metadata_key.strip():
                            session_key = metadata_key
                        continue

                    content = self._extract_content(row)
                    if not content:
                        continue
                    texts.append(content)
                    ts = row.get("timestamp")
                    if isinstance(ts, str):
                        if first_timestamp is None:
                            first_timestamp = ts
                        last_timestamp = ts

                    lowered = content.lower()
                    phrase_hits = lowered.count(phrase) if phrase else 0
                    term_hits = sum(lowered.count(term) for term in terms)
                    if phrase_hits or term_hits:
                        match_count += phrase_hits + term_hits
                        score += phrase_hits * 10 + term_hits
        except (OSError, UnicodeDecodeError):
            return None

        if score <= 0 or not texts:
            return None

        haystack = "\n".join(texts)
        excerpt = self._build_excerpt(
            haystack, phrase=phrase, terms=terms, excerpt_chars=excerpt_chars
        )
        return SessionSearchHit(
            session_key=session_key,
            path=path,
            score=score,
            match_count=match_count,
            excerpt=excerpt,
            first_timestamp=first_timestamp,
            last_timestamp=last_timestamp,
        )

    @staticmethod
    def _extract_content(row: dict[str, Any]) -> str:
        content = row.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            return "\n".join(parts)
        return ""

    @staticmethod
    def _build_excerpt(haystack: str, *, phrase: str, terms: list[str], excerpt_chars: int) -> str:
        lowered = haystack.lower()
        start = -1
        if phrase:
            start = lowered.find(phrase)
        if start < 0:
            starts = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
            start = min(starts) if starts else 0

        half = max(40, excerpt_chars // 2)
        left = max(0, start - half)
        right = min(len(haystack), start + half)
        excerpt = haystack[left:right].strip()
        if left > 0:
            excerpt = "..." + excerpt
        if right < len(haystack):
            excerpt = excerpt + "..."
        return excerpt
