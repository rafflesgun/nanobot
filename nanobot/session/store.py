"""SQLite session store with FTS5 for full-text search."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                model TEXT,
                title TEXT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                message_count INTEGER DEFAULT 0,
                token_count INTEGER DEFAULT 0,
                parent_session_id TEXT,
                FOREIGN KEY (parent_session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                role TEXT NOT NULL,
                content TEXT,
                timestamp TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                session_id, role, content,
                tokenize='porter unicode61'
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp);
            """
        )

    # -- Session CRUD ---------------------------------------------------------

    def create_session(
        self,
        session_id: str,
        source: str,
        model: str,
        started_at: str,
        parent_session_id: str | None = None,
    ) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO sessions (id, source, model, started_at, parent_session_id) VALUES (?, ?, ?, ?, ?)",
            (session_id, source, model, started_at, parent_session_id),
        )
        self.conn.commit()

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_session(self, session_id: str, **kwargs: Any) -> None:
        allowed = {"title", "ended_at", "message_count", "token_count", "model"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [session_id]
        self.conn.execute(
            f"UPDATE sessions SET {set_clause} WHERE id = ?", values
        )
        self.conn.commit()

    def list_sessions_rich(
        self,
        limit: int = 10,
        order_by_last_active: bool = True,
    ) -> list[dict[str, Any]]:
        if order_by_last_active:
            sql = """
                SELECT s.*, (SELECT MAX(timestamp) FROM messages WHERE session_id = s.id) AS last_active
                FROM sessions s
                ORDER BY last_active DESC
                LIMIT ?
            """
        else:
            sql = "SELECT *, NULL AS last_active FROM sessions ORDER BY id DESC LIMIT ?"
        rows = self.conn.execute(sql, (limit,)).fetchall()
        return [dict(r) for r in rows]

    # -- Messages -------------------------------------------------------------

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        timestamp: str,
    ) -> None:
        c = self.conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, timestamp),
        )
        self.conn.execute(
            "INSERT INTO messages_fts (rowid, session_id, role, content) VALUES (?, ?, ?, ?)",
            (c.lastrowid, session_id, role, content),
        )
        self.conn.execute(
            "UPDATE sessions SET message_count = message_count + 1 WHERE id = ?",
            (session_id,),
        )
        self.conn.commit()

    def search_messages(
        self,
        query: str,
        limit: int = 5,
        role_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        # Build FTS5 query: phrase match + individual prefix matches.
        # "retry loop" becomes '"retry loop" OR retry* OR loop*'
        # Phrase matches rank higher in BM25 than individual term matches.
        tokens = [t for t in query.split() if t]
        if not tokens:
            tokens = [query]
        phrase = '"' + " ".join(tokens) + '"'
        prefix_terms = " OR ".join(f"{t}*" for t in tokens)
        fts_query = f"{phrase} OR {prefix_terms}"
        conditions = ["messages_fts MATCH ?"]
        params: list[Any] = [fts_query]
        if role_filter:
            placeholders = ", ".join("?" for _ in role_filter)
            conditions.append(f"messages_fts.role IN ({placeholders})")
            params.extend(role_filter)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT messages_fts.session_id, messages_fts.role,
                   messages_fts.content, sessions.started_at as session_started,
                   sessions.source, sessions.model
            FROM messages_fts
            JOIN sessions ON sessions.id = messages_fts.session_id
            WHERE {where}
            ORDER BY rank
            LIMIT ?
        """
        params.append(limit)
        rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_messages_as_conversation(
        self, session_id: str
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Migration ------------------------------------------------------------

    def migrate_from_jsonl(self, sessions_dir: Path) -> int:
        """Import existing JSONL session files into SQLite. Returns count migrated."""
        if not sessions_dir.exists():
            return 0
        count = 0
        for path in sorted(sessions_dir.glob("*.jsonl")):
            session_id = path.stem
            started_at = None
            last_ts = None
            msgs: list[dict[str, str]] = []

            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("_type") == "metadata":
                    continue
                role = row.get("role", "user")
                content = row.get("content", "")
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            parts.append(item.get("text", ""))
                    content = "\n".join(parts)
                if not isinstance(content, str) or not content.strip():
                    continue
                ts = row.get("timestamp", "")
                msgs.append({"role": role, "content": content, "timestamp": ts})
                if started_at is None:
                    started_at = ts
                if ts:
                    last_ts = ts

            if not msgs:
                continue

            self.create_session(
                session_id=session_id,
                source="cli",
                model="unknown",
                started_at=started_at or last_ts or "unknown",
            )
            for msg in msgs:
                self.add_message(
                    session_id=session_id,
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=msg["timestamp"],
                )
            self.update_session(
                session_id,
                ended_at=last_ts or "",
                message_count=len(msgs),
            )
            count += 1
        return count

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
