"""Skill usage telemetry for Curator lifecycle decisions."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_ACTIVE = "active"
STATE_STALE = "stale"
STATE_ARCHIVED = "archived"
_VALID_STATES = {STATE_ACTIVE, STATE_STALE, STATE_ARCHIVED}


class SkillUsageStore:
    def __init__(self, usage_file: Path) -> None:
        self._path = usage_file

    def get(self, name: str) -> dict[str, Any] | None:
        return self._read().get(name)

    def bump_use(self, name: str) -> None:
        self._ensure_record(name)
        data = self._read()
        rec = data.get(name, {})
        rec["use_count"] = rec.get("use_count", 0) + 1
        now = _now_iso()
        rec["last_used_at"] = now
        data[name] = rec
        self._write(data)

    def bump_patch(self, name: str) -> None:
        self._ensure_record(name)
        data = self._read()
        rec = data.get(name, {})
        rec["patch_count"] = rec.get("patch_count", 0) + 1
        rec["last_patched_at"] = _now_iso()
        data[name] = rec
        self._write(data)

    def bump_view(self, name: str) -> None:
        self._ensure_record(name)
        data = self._read()
        rec = data.get(name, {})
        rec["view_count"] = rec.get("view_count", 0) + 1
        rec["last_viewed_at"] = _now_iso()
        data[name] = rec
        self._write(data)

    def set_state(self, name: str, state: str) -> None:
        if state not in _VALID_STATES:
            raise ValueError(f"invalid state '{state}'; must be one of {_VALID_STATES}")
        data = self._read()
        rec = data.get(name, {})
        rec["state"] = state
        data[name] = rec
        self._write(data)

    def set_pinned(self, name: str, pinned: bool) -> None:
        data = self._read()
        rec = data.get(name, {})
        rec["pinned"] = pinned
        data[name] = rec
        self._write(data)

    def latest_activity_at(self, record: dict[str, Any]) -> str | None:
        latest = None
        for key in ("last_used_at", "last_viewed_at", "last_patched_at"):
            val = record.get(key)
            if val and (latest is None or val > latest):
                latest = val
        return latest

    def _ensure_record(self, name: str) -> None:
        data = self._read()
        if name not in data:
            data[name] = {
                "created_at": _now_iso(),
                "state": STATE_ACTIVE,
                "pinned": False,
                "use_count": 0,
                "view_count": 0,
                "patch_count": 0,
            }
            self._write(data)

    def _read(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            dir=str(self._path.parent), prefix=".skill_usage_", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self._path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
