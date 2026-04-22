from nanobot.config.schema import Config
from nanobot.doctor.checks.channels import run_channel_checks


def test_channel_checks_only_inspect_enabled_channels() -> None:
    config = Config.model_validate(
        {
            "channels": {
                "telegram": {"enabled": True, "token": ""},
                "discord": {"enabled": False, "token": ""},
            }
        }
    )

    results = run_channel_checks(config, live=False)

    assert any(r.check_id == "telegram_config" for r in results)
    assert not any(r.check_id == "discord_config" for r in results)
