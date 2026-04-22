from nanobot.config.schema import Config
from nanobot.doctor.checks.providers import run_provider_checks


def test_provider_checks_warn_when_provider_block_missing() -> None:
    config = Config()
    config.agents.defaults.provider = "anthropic"
    config.agents.defaults.model = "anthropic/claude-opus-4-5"
    config.providers.anthropic.api_key = ""

    results = run_provider_checks(config, live=False)

    assert any(r.check_id == "provider_config" and r.status.value in {"warn", "fail"} for r in results)
