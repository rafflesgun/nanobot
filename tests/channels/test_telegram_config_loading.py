import json

from nanobot.bus.queue import MessageBus
from nanobot.channels.manager import ChannelManager
from nanobot.config.loader import load_config


def test_telegram_react_emoji_empty_survives_config_load(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "telegram": {
                        "enabled": True,
                        "token": "123:abc",
                        "allowFrom": ["*"],
                        "reactEmoji": "",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    manager = ChannelManager(config, MessageBus())
    channel = manager.channels["telegram"]

    assert channel.config.react_emoji == ""


def test_telegram_react_emoji_list_config_load(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "telegram": {
                        "enabled": True,
                        "token": "123:abc",
                        "allowFrom": ["*"],
                        "reactEmoji": ["⚡️", "👌", "👀"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    manager = ChannelManager(config, MessageBus())
    channel = manager.channels["telegram"]

    assert channel.config.react_emoji == ["⚡️", "👌", "👀"]


def test_telegram_react_emoji_empty_list_config_load(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "telegram": {
                        "enabled": True,
                        "token": "123:abc",
                        "allowFrom": ["*"],
                        "reactEmoji": [],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    manager = ChannelManager(config, MessageBus())
    channel = manager.channels["telegram"]

    assert channel.config.react_emoji == []


def test_telegram_react_emoji_default_is_list(tmp_path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "channels": {
                    "telegram": {
                        "enabled": True,
                        "token": "123:abc",
                        "allowFrom": ["*"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)
    manager = ChannelManager(config, MessageBus())
    channel = manager.channels["telegram"]

    assert channel.config.react_emoji == ["⚡️", "👌", "👀", "🔥", "👍"]
