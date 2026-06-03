"""Path utilities for nanobot configuration and data directories."""

import json
import logging
from pathlib import Path

<<<<<<< HEAD
from nanobot.config.loader import get_config_path
from nanobot.utils.helpers import ensure_dir, get_workspace_path

__all__ = ["get_workspace_path", "load_temperature_overrides", "save_temperature_overrides"]

logger = logging.getLogger(__name__)
=======
from nanobot.utils.helpers import ensure_dir
>>>>>>> origin/main


def get_config_path() -> Path:
    """Get the configuration file path (lazy import to break circular dependency).

    Delegates to ``nanobot.config.loader.get_config_path`` at call time so
    that importing this module never triggers a circular import during startup.
    """
    from nanobot.config.loader import get_config_path as _loader_get_config_path
    return _loader_get_config_path()


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


<<<<<<< HEAD
def get_media_dir(channel: str | None = None, workspace: str | Path | None = None) -> Path:
    """Get the media directory, optionally for a specific channel.
    
    When workspace is provided and is not the default workspace, media goes to
    workspace/media/ to ensure files are accessible within workspace restrictions.
    Otherwise, falls back to ~/.nanobot/media/
    """
    if workspace is not None and not is_default_workspace(workspace):
        base_dir = ensure_dir(Path(workspace).expanduser() / "media")
    else:
        base_dir = get_runtime_subdir("media")
    if channel:
        return ensure_dir(base_dir / channel)
    return base_dir


def get_overrides_file() -> Path:
    """Get the overrides persistence file path."""
    return get_data_dir() / "overrides.json"


def load_overrides() -> dict:
    """Load persisted overrides from disk."""
    overrides_file = get_overrides_file()
    if not overrides_file.exists():
        return {"model_overrides": {}, "tts_overrides": {}, "temperature_overrides": {}}
    try:
        data = json.loads(overrides_file.read_text(encoding="utf-8"))
        return {
            "model_overrides": data.get("model_overrides", {}),
            "tts_overrides": data.get("tts_overrides", {}),
            "temperature_overrides": data.get("temperature_overrides", {}),
        }
    except Exception:
        return {"model_overrides": {}, "tts_overrides": {}, "temperature_overrides": {}}


def save_overrides(overrides: dict) -> None:
    """Persist overrides to disk."""
    overrides_file = get_overrides_file()
    try:
        overrides_file.write_text(
            json.dumps(overrides, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("Failed to save overrides: {}", e)


def load_model_overrides() -> dict[str, str]:
    """Load model overrides from disk."""
    return load_overrides().get("model_overrides", {})


def save_model_overrides(model_overrides: dict[str, str]) -> None:
    """Save model overrides to disk."""
    overrides = load_overrides()
    overrides["model_overrides"] = model_overrides
    save_overrides(overrides)


def load_tts_overrides() -> dict[str, dict]:
    """Load TTS overrides from disk."""
    return load_overrides().get("tts_overrides", {})


def save_tts_overrides(tts_overrides: dict[str, dict]) -> None:
    """Save TTS overrides to disk."""
    overrides = load_overrides()
    overrides["tts_overrides"] = tts_overrides
    save_overrides(overrides)


def load_temperature_overrides() -> dict[str, float]:
    """Load temperature overrides from disk."""
    return load_overrides().get("temperature_overrides", {})


def save_temperature_overrides(temperature_overrides: dict[str, float]) -> None:
    """Save temperature overrides to disk."""
    overrides = load_overrides()
    overrides["temperature_overrides"] = temperature_overrides
    save_overrides(overrides)
=======
def get_webui_dir() -> Path:
    """Return the directory for WebUI-only persisted display threads (JSON)."""
    return get_runtime_subdir("webui")


def get_workspace_path(workspace: str | None = None) -> Path:
    """Resolve and ensure the agent workspace path."""
    path = Path(workspace).expanduser() if workspace else Path.home() / ".nanobot" / "workspace"
    return ensure_dir(path)
>>>>>>> origin/main


def is_default_workspace(workspace: str | Path | None) -> bool:
    """Return whether a workspace resolves to nanobot's default workspace path."""
    current = Path(workspace).expanduser() if workspace is not None else Path.home() / ".nanobot" / "workspace"
    default = Path.home() / ".nanobot" / "workspace"
    return current.resolve(strict=False) == default.resolve(strict=False)


def get_cli_history_path() -> Path:
    """Get the CLI history file path."""
    return Path.home() / ".nanobot" / "history" / "cli_history"


def get_bridge_install_dir() -> Path:
    """Get the bridge installation directory."""
    return Path.home() / ".nanobot" / "bridge"


def get_legacy_sessions_dir() -> Path:
    """Get the legacy sessions directory."""
    return Path.home() / ".nanobot" / "sessions"