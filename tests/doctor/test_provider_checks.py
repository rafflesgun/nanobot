from nanobot.config.schema import Config
from nanobot.doctor.checks.providers import run_provider_checks


def test_provider_checks_warn_when_provider_block_missing() -> None:
    config = Config()
    config.agents.defaults.provider = "anthropic"
    config.agents.defaults.model = "anthropic/claude-opus-4-5"
    config.providers.anthropic.api_key = ""

    results = run_provider_checks(config, live=False)

    assert any(r.check_id == "provider_config" and r.status.value in {"warn", "fail"} for r in results)


def test_provider_live_checks_call_probe_when_enabled(monkeypatch) -> None:
    config = Config()
    config.providers.openrouter.api_key = "sk-or-test"
    config.agents.defaults.model = "openrouter/anthropic/claude-opus-4-5"

    called = {"value": False}

    def _fake_probe(*_args, **_kwargs):
        called["value"] = True
        return True, "ok"

    monkeypatch.setattr("nanobot.doctor.checks.providers._probe_provider", _fake_probe)

    run_provider_checks(config, live=True)

    assert called["value"] is True
