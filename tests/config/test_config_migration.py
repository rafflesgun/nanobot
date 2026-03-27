import json

from nanobot.config.loader import load_config, save_config


def test_load_config_keeps_max_tokens_and_ignores_legacy_memory_window(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "maxTokens": 1234,
                        "memoryWindow": 42,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.agents.defaults.max_tokens == 1234
    assert config.agents.defaults.context_window_tokens == 65_536
    assert not hasattr(config.agents.defaults, "memory_window")


def test_save_config_writes_context_window_tokens_but_not_memory_window(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "maxTokens": 2222,
                        "memoryWindow": 30,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    save_config(config, config_path)
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    defaults = saved["agents"]["defaults"]

    assert defaults["maxTokens"] == 2222
    assert defaults["contextWindowTokens"] == 65_536
    assert "memoryWindow" not in defaults


def test_onboard_does_not_crash_with_legacy_memory_window(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "maxTokens": 3333,
                        "memoryWindow": 50,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda _workspace=None: workspace)

    from typer.testing import CliRunner
    from nanobot.cli.commands import app
    runner = CliRunner()
    result = runner.invoke(app, ["onboard"], input="n\n")

    assert result.exit_code == 0


def test_onboard_refresh_backfills_missing_channel_fields(tmp_path, monkeypatch) -> None:
    from types import SimpleNamespace

    config_path = tmp_path / "config.json"
    workspace = tmp_path / "workspace"
    config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "qq": {
                        "enabled": False,
                        "appId": "",
                        "secret": "",
                        "allowFrom": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr("nanobot.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("nanobot.cli.commands.get_workspace_path", lambda _workspace=None: workspace)
    monkeypatch.setattr(
        "nanobot.channels.registry.discover_all",
        lambda: {
            "qq": SimpleNamespace(
                default_config=lambda: {
                    "enabled": False,
                    "appId": "",
                    "secret": "",
                    "allowFrom": [],
                    "msgFormat": "plain",
                }
            )
        },
    )

    from typer.testing import CliRunner
    from nanobot.cli.commands import app
    runner = CliRunner()
    result = runner.invoke(app, ["onboard"], input="n\n")

    assert result.exit_code == 0
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["channels"]["qq"]["msgFormat"] == "plain"


def test_load_config_migrates_exec_restrict_to_workspace_bool(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "tools": {
                    "exec": {
                        "restrictToWorkspace": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.tools.restrict_to_workspace.enabled is True
    assert config.tools.restrict_to_workspace.extra_read == []
    assert config.tools.restrict_to_workspace.extra_write == []


def test_load_config_migrates_top_level_restrict_to_workspace_bool(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "tools": {
                    "restrictToWorkspace": True,
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.tools.restrict_to_workspace.enabled is True
    assert config.tools.restrict_to_workspace.extra_read == []
    assert config.tools.restrict_to_workspace.extra_write == []


def test_save_config_writes_nested_workspace_restriction_shape(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config = load_config(config_path)
    config.tools.restrict_to_workspace.enabled = True
    config.tools.restrict_to_workspace.extra_read = ["/tmp/read-only"]
    config.tools.restrict_to_workspace.extra_write = ["/tmp/read-write"]

    save_config(config, config_path)
    saved = json.loads(config_path.read_text(encoding="utf-8"))

    assert saved["tools"]["restrictToWorkspace"] == {
        "enabled": True,
        "extraRead": ["/tmp/read-only"],
        "extraWrite": ["/tmp/read-write"],
    }


def test_load_config_accepts_ordered_fallback_models(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "fallbackModel": "legacy-fallback",
                        "fallbackModels": ["backup-a", "backup-b"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.agents.defaults.fallback_model == "legacy-fallback"
    assert config.agents.defaults.fallback_models == ["backup-a", "backup-b"]


def test_save_config_writes_ordered_fallback_models(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config = load_config(config_path)
    config.agents.defaults.fallback_model = "legacy-fallback"
    config.agents.defaults.fallback_models = ["backup-a", "backup-b"]

    save_config(config, config_path)
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    defaults = saved["agents"]["defaults"]

    assert defaults["fallbackModel"] == "legacy-fallback"
    assert defaults["fallbackModels"] == ["backup-a", "backup-b"]


def test_load_config_preserves_named_agent_profiles(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "agents": {
                    "defaults": {
                        "model": "main-model",
                        "temperature": 0.4,
                    },
                    "research": {
                        "model": "research-model",
                        "temperature": 0.1,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    resolved = config.agents.resolve("research")

    assert resolved.model == "research-model"
    assert resolved.temperature == 0.1
    assert config.agents.agent_ids() == ["defaults", "research"]
