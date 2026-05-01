"""Tracks skill usage across sessions (for sub-agent auditing)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SkillUsageStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, Any] | None = None

    @property
    def data(self) -> dict[str, Any]:
        if self._data is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                self._data = {}
        return self._data

    def record_usage(self, skill_name: str, session_id: str) -> None:
        self.data.setdefault(skill_name, {})
        self.data[skill_name].setdefault("count", 0)
        self.data[skill_name]["count"] += 1
        self.data[skill_name].setdefault("sessions", [])
        if session_id not in self.data[skill_name]["sessions"]:
            self.data[skill_name]["sessions"].append(session_id)
        self._save()

    def get_usage(self, skill_name: str) -> dict[str, Any] | None:
        return self.data.get(skill_name)

    def _save(self) -> None:
        try:
            self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            logger.exception("Failed to save skill usage to %s", self.path)
