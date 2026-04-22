"""Doctor checks for MCP server configuration."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from nanobot.agent.tools.mcp import connect_mcp_servers
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.config.schema import Config, MCPServerConfig
from nanobot.doctor.types import DoctorCheckResult, DoctorStatus

_SECTION = "mcp"
_TRANSPORTS = {"stdio", "sse", "streamableHttp"}


def run_mcp_checks(config: Config, *, live: bool) -> list[DoctorCheckResult]:
    """Validate MCP config blocks using local shape checks only."""
    results: list[DoctorCheckResult] = []

    for name, server_cfg in sorted(config.tools.mcp_servers.items()):
        results.append(_check_server(name, server_cfg))

        if live:
            try:
                ok, message = asyncio.run(_probe_mcp_server(name, server_cfg))
            except RuntimeError as exc:
                ok = False
                message = f"MCP live probe failed: {exc}"
            except Exception as exc:
                ok = False
                message = f"MCP live probe failed: {type(exc).__name__}: {exc}"

            results.append(
                DoctorCheckResult(
                    section=_SECTION,
                    check_id=f"mcp_{name}_live",
                    status=DoctorStatus.OK if ok else DoctorStatus.WARN,
                    message=message,
                    hint=None if ok else "Verify the MCP server command or URL and confirm it accepts connections.",
                )
            )

    return results


def _check_server(name: str, server_cfg: MCPServerConfig) -> DoctorCheckResult:
    enabled_tools = list(server_cfg.enabled_tools)
    transport = _transport_type(server_cfg)
    missing: list[str] = []

    if transport not in _TRANSPORTS:
        missing.append("transport")
    elif transport == "stdio" and not server_cfg.command.strip():
        missing.append("command")
    elif transport in {"sse", "streamableHttp"} and not server_cfg.url.strip():
        missing.append("url")

    unmatched_tools = _unmatched_enabled_tools(name, enabled_tools)
    if missing:
        return DoctorCheckResult(
            section=_SECTION,
            check_id=f"mcp_{name}_config",
            status=DoctorStatus.FAIL,
            message=f"MCP server '{name}' is missing required config: {', '.join(missing)}",
            hint="Fill in the required stdio or HTTP transport fields.",
        )

    if unmatched_tools:
        return DoctorCheckResult(
            section=_SECTION,
            check_id=f"mcp_{name}_config",
            status=DoctorStatus.WARN,
            message=(
                f"MCP server '{name}' has enabledTools entries that cannot be validated locally: "
                f"{', '.join(unmatched_tools)}"
            ),
            hint="Use '*' or verify the raw/wrapped tool names against the running MCP server.",
        )

    return DoctorCheckResult(
        section=_SECTION,
        check_id=f"mcp_{name}_config",
        status=DoctorStatus.OK,
        message=f"MCP server '{name}' has a locally valid config block.",
    )


def _transport_type(server_cfg: MCPServerConfig) -> str:
    if server_cfg.type:
        return server_cfg.type
    if server_cfg.url.strip():
        return "sse"
    if server_cfg.command.strip():
        return "stdio"
    return ""


def _unmatched_enabled_tools(server_name: str, enabled_tools: list[str]) -> list[str]:
    if not enabled_tools or "*" in enabled_tools:
        return []

    unmatched: list[str] = []
    wrapped_prefix = f"mcp_{server_name}_"
    for tool_name in enabled_tools:
        if not tool_name.strip():
            unmatched.append(tool_name)
            continue
        if tool_name.startswith(wrapped_prefix):
            continue
        unmatched.append(tool_name)
    return unmatched


async def _probe_mcp_server(name: str, server_cfg: MCPServerConfig) -> tuple[bool, str]:
    registry = ToolRegistry()
    stacks = await connect_mcp_servers({name: server_cfg}, registry)
    stack = stacks.get(name)
    if stack is None:
        return False, f"MCP live probe could not connect to server '{name}'."

    with suppress(Exception):
        await stack.aclose()

    return True, f"MCP live probe connected to server '{name}'."
