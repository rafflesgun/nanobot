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
