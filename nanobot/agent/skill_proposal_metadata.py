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
                "last_scan_verdict": verdict,
                "last_scan_summary": summary,
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

    def _ensure_dir(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            import logging
            logging.getLogger(__name__).warning("Corrupted metadata file %s, resetting", self.path)
            return {}
        except OSError:
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        self._ensure_dir()
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=self.path.parent)
        try:
            tmp.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
            tmp.close()
            os.replace(tmp.name, self.path)
        except BaseException:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass
            raise

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
