"""Token usage statistics manager."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from loguru import logger


class StatsManager:
    """Manages token usage statistics for the nanobot."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.stats_dir = workspace / "stats"
        self.usage_file = self.stats_dir / "usage.jsonl"
        self._ensure_stats_dir()

    def _ensure_stats_dir(self) -> None:
        """Ensure the stats directory exists."""
        self.stats_dir.mkdir(parents=True, exist_ok=True)

    def record_usage(self, channel: str, chat_id: str, model: str, input_tokens: int, output_tokens: int,
                     total_tokens: int, session_key: str, timestamp: str = None) -> None:
        """Record token usage statistics."""
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        stats_data = {
            "timestamp": timestamp,
            "channel": channel,
            "chat_id": chat_id,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "session_key": session_key
        }

        # Append to the usage file in JSONL format
        with open(self.usage_file, "a") as f:
            f.write(json.dumps(stats_data) + "\n")

    def get_stats(self, channel: str = None, chat_id: str = None) -> Dict[str, Any]:
        """Get token usage statistics for a specific channel/chat_id combination."""
        if not self.usage_file.exists():
            return {}

        stats = {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "count": 0
        }

        try:
            with open(self.usage_file, "r") as f:
                for line in f:
                    if not line.strip():
                        continue
                    data = json.loads(line)

                    # Filter by channel and chat_id if provided
                    if channel and data.get("channel") != channel:
                        continue
                    if chat_id and data.get("chat_id") != chat_id:
                        continue

                    stats["total_input_tokens"] += data.get("input_tokens", 0)
                    stats["total_output_tokens"] += data.get("output_tokens", 0)
                    stats["total_tokens"] += data.get("total_tokens", 0)
                    stats["count"] += 1

        except Exception as e:
            logger.error(f"Error reading stats file: {e}")
            return {}

        return stats

    def get_all_stats(self) -> Dict[str, Any]:
        """Get all token usage statistics."""
        return self.get_stats()