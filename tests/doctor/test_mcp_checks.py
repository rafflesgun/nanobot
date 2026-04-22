import asyncio

from nanobot.config.schema import Config
from nanobot.doctor.checks.mcp import run_mcp_checks


def test_mcp_checks_warn_on_unmatched_enabled_tools() -> None:
    config = Config.model_validate(
        {
            "tools": {
                "mcpServers": {
                    "demo": {
                        "enabled": True,
                        "transport": "stdio",
                        "command": "python",
                        "args": ["server.py"],
                        "enabledTools": ["missing_tool"],
                    }
                }
            }
        }
    )

    results = run_mcp_checks(config, live=False)

    assert any(r.check_id == "mcp_demo_config" for r in results)


def test_mcp_live_checks_attempt_probe_when_enabled(monkeypatch) -> None:
    config = Config.model_validate(
        {
            "tools": {
                "mcpServers": {
                    "demo": {
                        "enabled": True,
                        "transport": "stdio",
                        "command": "python",
                        "args": ["server.py"],
                    }
                }
            }
        }
    )

    called = {"value": False}

    async def _fake_probe(*_args, **_kwargs):
        called["value"] = True
        return True, "connected"

    monkeypatch.setattr("nanobot.doctor.checks.mcp._probe_mcp_server", _fake_probe)

    results = run_mcp_checks(config, live=True)

    assert called["value"] is True
    assert any(r.check_id == "mcp_demo_live" for r in results)


def test_mcp_live_checks_translate_probe_errors_to_results(monkeypatch) -> None:
    config = Config.model_validate(
        {
            "tools": {
                "mcpServers": {
                    "demo": {
                        "enabled": True,
                        "transport": "stdio",
                        "command": "python",
                        "args": ["server.py"],
                    }
                }
            }
        }
    )

    async def _fake_probe(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("nanobot.doctor.checks.mcp._probe_mcp_server", _fake_probe)

    results = run_mcp_checks(config, live=True)

    live_result = next(r for r in results if r.check_id == "mcp_demo_live")
    assert live_result.status.value == "fail"
    assert "boom" in live_result.message


def test_mcp_live_checks_translate_timeouts_to_fail_results(monkeypatch) -> None:
    config = Config.model_validate(
        {
            "tools": {
                "mcpServers": {
                    "demo": {
                        "enabled": True,
                        "transport": "stdio",
                        "command": "python",
                        "args": ["server.py"],
                    }
                }
            }
        }
    )

    async def _fake_probe(*_args, **_kwargs):
        raise asyncio.TimeoutError("timed out")

    monkeypatch.setattr("nanobot.doctor.checks.mcp._probe_mcp_server", _fake_probe)

    results = run_mcp_checks(config, live=True)

    live_result = next(r for r in results if r.check_id == "mcp_demo_live")
    assert live_result.status.value == "fail"
    assert "timed out" in live_result.message.lower()
