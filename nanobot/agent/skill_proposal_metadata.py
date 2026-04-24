"""Metadata store for skill proposal lifecycle state."""

from __future__ import annotations

import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


class ProposalMetadataStore:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.dir = workspace / "memory" / "skill-proposals"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / ".metadata.json"

    def get(self, name: str) -> dict[str, Any] | None:
        return self._read().get(name)

    def list(self) -> dict[str, dict[str, Any]]:
        return self._read()

    def record_created(self, name: str, source: str) -> None:
        data = self._read()
        entry = data.get(name, {})
        entry.update(
            {
                "status": "pending",
                "source": source,
                "created_at": entry.get("created_at", self._timestamp()),
            }
        )
        data[name] = entry
        self._write(data)

    def record_scan(self, name: str, verdict: str, summary: str) -> None:
        data = self._read()
        entry = data.get(name, {})
        entry.update(
            {
                "scan_verdict": verdict,
                "scan_summary": summary,
                "scanned_at": self._timestamp(),
            }
        )
        data[name] = entry
        self._write(data)

    def record_applied(self, name: str) -> None:
        data = self._read()
        entry = data.get(name, {})
        entry.update(
            {
                "status": "applied",
                "applied_at": self._timestamp(),
            }
        )
        data[name] = entry
        self._write(data)

    def record_rejected(self, name: str) -> None:
        data = self._read()
        entry = data.get(name, {})
        entry.update(
            {
                "status": "rejected",
                "rejected_at": self._timestamp(),
            }
        )
        data[name] = entry
        self._write(data)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
