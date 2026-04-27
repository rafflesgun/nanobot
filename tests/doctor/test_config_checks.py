import json
from pathlib import Path

from nanobot.doctor.checks.config import run_config_checks


def test_config_checks_report_missing_file(tmp_path: Path) -> None:
    results = run_config_checks(tmp_path / "missing.json")
    assert any(r.check_id == "config_exists" and r.status.value == "fail" for r in results)


def test_config_checks_report_unresolved_env_var(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({
            "channels": {"telegram": {"enabled": True, "token": "${TELEGRAM_TOKEN}"}},
        }),
        encoding="utf-8",
    )
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)

    results = run_config_checks(config_path)
    assert any(r.check_id == "env_resolution" and r.status.value == "fail" for r in results)


def test_config_checks_report_invalid_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{not valid json", encoding="utf-8")

    results = run_config_checks(config_path)
    assert any(r.check_id == "config_parse" and r.status.value == "fail" for r in results)


def test_config_checks_report_directory_path_as_parse_failure(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.mkdir()

    results = run_config_checks(config_path)

    assert any(r.check_id == "config_parse" and r.status.value == "fail" for r in results)


def test_config_checks_report_schema_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    # agents.defaults.maxTokens must be an int, not a string
    config_path.write_text(
        json.dumps({"agents": {"defaults": {"maxTokens": "not_a_number"}}}),
        encoding="utf-8",
    )

    results = run_config_checks(config_path)
    assert any(r.check_id == "config_validate" and r.status.value == "fail" for r in results)


def test_config_checks_all_pass_for_valid_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({}), encoding="utf-8")

    results = run_config_checks(config_path)
    assert all(r.status.value == "ok" for r in results)
    assert any(r.check_id == "config_exists" for r in results)
    assert any(r.check_id == "config_parse" for r in results)
    assert any(r.check_id == "config_validate" for r in results)
    assert any(r.check_id == "env_resolution" for r in results)


def test_config_checks_resolved_env_var_passes(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({
            "channels": {"telegram": {"enabled": True, "token": "${TELEGRAM_TOKEN}"}},
        }),
        encoding="utf-8",
    )
    monkeypatch.setenv("TELEGRAM_TOKEN", "test-token-123")

    results = run_config_checks(config_path)
    assert any(r.check_id == "env_resolution" and r.status.value == "ok" for r in results)
