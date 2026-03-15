"""Path utilities for nanobot configuration and data directories."""

from pathlib import Path

from nanobot.config.loader import get_config_path
from nanobot.utils.helpers import ensure_dir


def get_data_dir() -> Path:
    """Get the nanobot data directory."""
    return ensure_dir(get_config_path().parent)


def get_runtime_subdir(subdir: str) -> Path:
    """Get a runtime subdirectory under the data directory."""
    return ensure_dir(get_data_dir() / subdir)


def get_cron_dir() -> Path:
    """Get the cron directory."""
    return get_runtime_subdir("cron")


def get_logs_dir() -> Path:
    """Get the logs directory."""
    return get_runtime_subdir("logs")


def get_media_dir(channel: str | None = None) -> Path:
    """Get the media directory, optionally for a specific channel."""
    base_dir = get_runtime_subdir("media")
    if channel:
        return ensure_dir(base_dir / channel)
    return base_dir


def get_cli_history_path() -> Path:
    """Get the CLI history file path."""
    return Path.home() / ".nanobot" / "history" / "cli_history"


def get_bridge_install_dir() -> Path:
    """Get the bridge installation directory."""
    return Path.home() / ".nanobot" / "bridge"


def get_legacy_sessions_dir() -> Path:
    """Get the legacy sessions directory."""
    return Path.home() / ".nanobot" / "sessions"