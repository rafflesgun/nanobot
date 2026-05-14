"""Small HTTP surface for gateway health and admin API routes."""

from __future__ import annotations

import asyncio
import json
import re
import time
import yaml
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from nanobot.admin.auth import is_authorized
from nanobot.agent.subagents import AgentLoader
from nanobot.config.schema import Config
from nanobot.session.manager import SessionManager

_MAX_REQUEST_HEADER_BYTES = 65536
_MAX_REQUEST_BODY_BYTES = 1024 * 1024
_MAX_LOG_TAIL_BYTES = 256 * 1024
_SUBAGENT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class AdminContext:
    config: Config
    session_manager: SessionManager
    enabled_channels: list[str]
    start_time: float


def _json_response(payload: dict[str, Any], *, status: int = 200) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    reason = HTTPStatus(status).phrase
    return (
        f"HTTP/1.0 {status} {reason}\r\n"
        "Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "X-Content-Type-Options: nosniff\r\n"
        "\r\n"
    ).encode("utf-8") + body


def _text_response(body: str, *, status: int = 200) -> bytes:
    encoded = body.encode("utf-8")
    reason = HTTPStatus(status).phrase
    return (
        f"HTTP/1.0 {status} {reason}\r\n"
        "Content-Type: text/plain\r\n"
        f"Content-Length: {len(encoded)}\r\n"
        "\r\n"
    ).encode("utf-8") + encoded


def _parse_request(raw: bytes) -> tuple[str, str, dict[str, str], bytes]:
    head_raw, _, body = raw.partition(b"\r\n\r\n")
    head = head_raw.decode("utf-8", errors="replace")
    lines = head.split("\r\n")
    request_line = lines[0] if lines else ""
    parts = request_line.split(" ")
    method = parts[0] if len(parts) >= 1 else ""
    target = parts[1] if len(parts) >= 2 else ""
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        headers[name.strip()] = value.strip()
    return method, target, headers, body


async def _read_http_header(reader: asyncio.StreamReader, *, timeout_s: float) -> bytes:
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout_s)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > _MAX_REQUEST_HEADER_BYTES:
            break

    head_raw, separator, body = bytes(data).partition(b"\r\n\r\n")
    if not separator:
        return bytes(data)

    content_length = 0
    head = head_raw.decode("utf-8", errors="replace")
    for line in head.split("\r\n")[1:]:
        name, _, value = line.partition(":")
        if name.strip().lower() != "content-length":
            continue
        try:
            content_length = min(max(0, int(value.strip())), _MAX_REQUEST_BODY_BYTES)
        except ValueError:
            content_length = 0
        break

    while len(body) < content_length:
        chunk = await asyncio.wait_for(reader.read(content_length - len(body)), timeout=timeout_s)
        if not chunk:
            break
        data.extend(chunk)
        body += chunk
    return bytes(data)


def _status_payload(ctx: AdminContext) -> dict[str, Any]:
    provider_name = ctx.config.get_provider_name(ctx.config.agents.defaults.model)
    return {
        "status": "ok",
        "admin_api": {"version": "v1"},
        "uptime_s": round(time.monotonic() - ctx.start_time, 3),
        "model": ctx.config.agents.defaults.model,
        "provider": ctx.config.agents.defaults.provider,
        "resolved_provider": provider_name,
        "channels": list(ctx.enabled_channels),
        "websocket": {
            "enabled": bool(getattr(getattr(ctx.config.channels, "websocket", None), "enabled", False)),
        },
    }


def _decode_session_key(raw_key: str, ctx: AdminContext) -> str | None:
    key = unquote(raw_key)
    if not key or "\x00" in key:
        return None
    session_path = ctx.session_manager._get_session_path(key).resolve()
    sessions_dir = ctx.session_manager.sessions_dir.resolve()
    if session_path.parent != sessions_dir:
        return None
    return key


def _sessions_payload(ctx: AdminContext, query: str) -> dict[str, Any]:
    params = parse_qs(query)
    channel = (params.get("channel") or [""])[0]
    limit_raw = (params.get("limit") or ["50"])[0]
    try:
        limit = max(1, min(int(limit_raw), 200))
    except ValueError:
        limit = 50
    sessions = []
    for item in ctx.session_manager.list_sessions():
        key = item.get("key")
        if not isinstance(key, str):
            continue
        if channel and not key.startswith(f"{channel}:"):
            continue
        sessions.append({k: v for k, v in item.items() if k != "path"})
        if len(sessions) >= limit:
            break
    return {"sessions": sessions, "next_cursor": None}


def _get_config_payload(ctx: AdminContext) -> dict[str, Any]:
    from nanobot.config.loader import get_config_path

    path = get_config_path()
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return ctx.config.model_dump(mode="json", by_alias=True)


def _put_config(ctx: AdminContext, body: bytes) -> tuple[dict[str, Any], int]:
    from nanobot.config.loader import get_config_path

    try:
        data = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {"error": "invalid json"}, 400
    if not isinstance(data, dict):
        return {"error": "json object required"}, 400
    try:
        Config.model_validate(data)
    except Exception as exc:
        return {"error": f"invalid config: {exc}"}, 400
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    ctx.config = Config.model_validate(data)
    return data, 200


def _builtin_agents_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "agents"


def _workspace_agents_dir(ctx: AdminContext) -> Path:
    return ctx.config.workspace_path / "agents"


def _safe_subagent_name(raw_name: str) -> str | None:
    name = unquote(raw_name)
    if not _SUBAGENT_NAME_RE.match(name):
        return None
    return name


def _subagent_path(ctx: AdminContext, name: str) -> Path:
    root = _workspace_agents_dir(ctx).resolve()
    path = (root / f"{name}.md").resolve()
    path.relative_to(root)
    return path


def _parse_subagent_content(content: str, fallback_name: str) -> tuple[dict[str, Any], str]:
    frontmatter: dict[str, Any] = {}
    body = content.strip()
    match = _FRONTMATTER_RE.match(content)
    if match:
        loaded = yaml.safe_load(match.group(1)) or {}
        if not isinstance(loaded, dict):
            raise ValueError("frontmatter object required")
        frontmatter = loaded
        body = content[match.end():].strip()
    if not body:
        raise ValueError("prompt body is required")
    name = frontmatter.get("name", fallback_name)
    if not isinstance(name, str) or not name:
        raise ValueError("subagent name is required")
    description = frontmatter.get("description", "")
    if description is not None and not isinstance(description, str):
        raise ValueError("description must be a string")
    model = frontmatter.get("model", "")
    if model is not None and not isinstance(model, str):
        raise ValueError("model must be a string")
    tools = frontmatter.get("tools") or []
    if not isinstance(tools, list) or any(not isinstance(tool, str) for tool in tools):
        raise ValueError("tools must be a list of strings")
    for key in ("max_iterations", "max_tokens"):
        if key in frontmatter:
            try:
                int(frontmatter[key])
            except (TypeError, ValueError):
                raise ValueError(f"{key} must be numeric") from None
    return frontmatter, body


def _subagent_meta(config: Any, *, source: str, editable: bool) -> dict[str, Any]:
    return {
        "name": config.name,
        "description": config.description,
        "model": config.model,
        "tools": list(config.tools),
        "max_iterations": config.max_iterations,
        "max_tokens": config.max_tokens,
        "source": source,
        "editable": editable,
    }


def _subagents_payload(ctx: AdminContext) -> dict[str, Any]:
    loader = AgentLoader(_workspace_agents_dir(ctx), _builtin_agents_dir())
    items = []
    for config in loader.list_all():
        source = "workspace" if (_workspace_agents_dir(ctx) / f"{config.name}.md").exists() else "builtin"
        items.append(_subagent_meta(config, source=source, editable=source == "workspace"))
    return {"subagents": items}


def _read_subagent_payload(ctx: AdminContext, raw_name: str) -> tuple[dict[str, Any], int]:
    name = _safe_subagent_name(raw_name)
    if name is None:
        return {"error": "invalid subagent name"}, 400
    loader = AgentLoader(_workspace_agents_dir(ctx), _builtin_agents_dir())
    config = loader.load(name)
    if config is None:
        return {"error": "subagent not found"}, 404
    workspace_path = _workspace_agents_dir(ctx) / f"{name}.md"
    source = "workspace" if workspace_path.exists() else "builtin"
    read_path = workspace_path if source == "workspace" else _builtin_agents_dir() / f"{name}.md"
    payload = _subagent_meta(config, source=source, editable=source == "workspace")
    payload["content"] = read_path.read_text(encoding="utf-8")
    return payload, 200


def _write_subagent(ctx: AdminContext, raw_name: str, body: bytes) -> tuple[dict[str, Any], int]:
    name = _safe_subagent_name(raw_name)
    if name is None:
        return {"error": "invalid subagent name"}, 400
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {"error": "invalid json"}, 400
    content = payload.get("content") if isinstance(payload, dict) else None
    if not isinstance(content, str):
        return {"error": "content is required"}, 400
    match = _FRONTMATTER_RE.match(content)
    if match:
        try:
            loaded_name = (yaml.safe_load(match.group(1)) or {}).get("name")
        except (AttributeError, yaml.YAMLError):
            loaded_name = None
        if isinstance(loaded_name, str) and loaded_name != name:
            return {"error": "subagent name mismatch"}, 400
    try:
        frontmatter, _ = _parse_subagent_content(content, name)
    except (ValueError, yaml.YAMLError) as exc:
        return {"error": str(exc)}, 400
    if frontmatter.get("name", name) != name:
        return {"error": "subagent name mismatch"}, 400
    agents_dir = _workspace_agents_dir(ctx)
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = _subagent_path(ctx, name)
    path.write_text(content, encoding="utf-8")
    loader = AgentLoader(agents_dir, _builtin_agents_dir())
    config = loader.load(name)
    return {"subagent": _subagent_meta(config, source="workspace", editable=True)}, 200


def _delete_subagent(ctx: AdminContext, raw_name: str) -> tuple[dict[str, Any], int]:
    name = _safe_subagent_name(raw_name)
    if name is None:
        return {"error": "invalid subagent name"}, 400
    path = _subagent_path(ctx, name)
    if not path.exists():
        if (_builtin_agents_dir() / f"{name}.md").exists():
            return {"error": "read-only subagent"}, 403
        return {"deleted": False}, 200
    path.unlink()
    return {"deleted": True}, 200


def _zero_usage(days: int) -> dict[str, Any]:
    return {
        "range": {"days": days},
        "totals": {"count": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cached_tokens": 0},
        "by_day": [],
        "by_model": [],
        "by_channel": [],
        "by_session": [],
        "pricing": {"configured": False, "message": "Pricing is not configured; showing token usage only."},
    }


def _usage_days(query: str) -> int:
    raw = (parse_qs(query).get("days") or ["30"])[0]
    try:
        return max(1, min(int(raw), 366))
    except ValueError:
        return 30


def _usage_row(key: str) -> dict[str, Any]:
    return {"key": key, "count": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cached_tokens": 0}


def _add_usage(row: dict[str, Any], data: dict[str, Any]) -> None:
    row["count"] += 1
    row["input_tokens"] += int(data.get("input_tokens") or 0)
    row["output_tokens"] += int(data.get("output_tokens") or 0)
    row["total_tokens"] += int(data.get("total_tokens") or 0)
    row["cached_tokens"] += int(data.get("cached_tokens") or 0)


def _usage_payload(ctx: AdminContext, query: str) -> dict[str, Any]:
    params = parse_qs(query)
    days = _usage_days(query)
    payload = _zero_usage(days)
    path = ctx.config.workspace_path / "stats" / "usage.jsonl"
    if not path.exists():
        return payload
    filters = {
        "channel": (params.get("channel") or [None])[0],
        "session_key": (params.get("session_key") or [None])[0],
        "model": (params.get("model") or [None])[0],
    }
    groups: dict[str, dict[str, dict[str, Any]]] = {"by_day": {}, "by_model": {}, "by_channel": {}, "by_session": {}}
    skipped = 0
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if filters["channel"] and data.get("channel") != filters["channel"]:
                continue
            if filters["session_key"] and data.get("session_key") != filters["session_key"]:
                continue
            if filters["model"] and data.get("model") != filters["model"]:
                continue
            _add_usage(payload["totals"], data)
            day = str(data.get("timestamp", ""))[:10] or "unknown"
            model = str(data.get("model") or "unknown")
            channel = str(data.get("channel") or "unknown")
            session = str(data.get("session_key") or "unknown")
            for bucket, key in (("by_day", day), ("by_model", model), ("by_channel", channel), ("by_session", session)):
                row = groups[bucket].setdefault(key, _usage_row(key))
                _add_usage(row, data)
    for bucket in groups:
        payload[bucket] = sorted(groups[bucket].values(), key=lambda row: row["key"])
    if skipped:
        payload["warnings"] = [{"skipped_lines": skipped}]
    return payload


def _log_dir(ctx: AdminContext) -> Any:
    return ctx.config.workspace_path / "logs"


def _safe_log_name(name: str) -> bool:
    return bool(re.match(r"^[A-Za-z0-9_.-]+$", name)) and name.endswith(".log")


def _logs_payload(ctx: AdminContext) -> dict[str, Any]:
    root = _log_dir(ctx)
    logs = []
    if root.exists():
        for path in sorted(root.glob("*.log")):
            if path.is_file():
                logs.append({"name": path.name})
    return {"logs": logs}


def _tail_lines(path: Path, tail: int) -> list[str]:
    if tail <= 0:
        return []
    chunks: list[bytes] = []
    newline_count = 0
    chunk_size = 8192
    bytes_read = 0
    with path.open("rb") as fh:
        position = fh.seek(0, 2)
        while position > 0 and newline_count <= tail and bytes_read < _MAX_LOG_TAIL_BYTES:
            read_size = min(chunk_size, position, _MAX_LOG_TAIL_BYTES - bytes_read)
            position -= read_size
            fh.seek(position)
            chunk = fh.read(read_size)
            chunks.append(chunk)
            bytes_read += len(chunk)
            newline_count += chunk.count(b"\n")
    return b"".join(reversed(chunks)).decode("utf-8", errors="replace").splitlines()[-tail:]


def _tail_log_payload(ctx: AdminContext, name: str, query: str) -> tuple[dict[str, Any], int]:
    if not _safe_log_name(name):
        return {"error": "invalid log name"}, 400
    params = parse_qs(query)
    tail_raw = (params.get("tail") or ["200"])[0]
    try:
        tail = max(1, min(int(tail_raw), ctx.config.gateway.admin.max_log_tail_lines))
    except ValueError:
        tail = min(200, ctx.config.gateway.admin.max_log_tail_lines)
    path = (_log_dir(ctx) / name).resolve()
    try:
        path.relative_to(_log_dir(ctx).resolve())
    except ValueError:
        return {"error": "not found"}, 404
    if not path.is_file():
        return {"error": "not found"}, 404
    lines = _tail_lines(path, tail)
    return {"name": name, "lines": lines}, 200


async def handle_http_request(raw: bytes, ctx: AdminContext) -> bytes:
    method, target, headers, body = _parse_request(raw)
    parsed = urlparse(target)
    path = parsed.path or "/"

    if method == "GET" and path == "/health":
        return _json_response({"status": "ok"})

    if not path.startswith("/admin/v1"):
        return _text_response("Not Found", status=404)

    admin_cfg = ctx.config.gateway.admin
    if not is_authorized(headers, enabled=admin_cfg.enabled, configured_token=admin_cfg.token):
        return _json_response({"error": "Unauthorized"}, status=401)

    if method == "GET" and path == "/admin/v1/status":
        return _json_response(_status_payload(ctx))

    if method == "GET" and path == "/admin/v1/sessions":
        return _json_response(_sessions_payload(ctx, parsed.query))

    m = re.match(r"^/admin/v1/sessions/([^/]+)/messages$", path)
    if method == "GET" and m:
        key = _decode_session_key(m.group(1), ctx)
        if key is None:
            return _json_response({"error": "invalid session key"}, status=400)
        payload = ctx.session_manager.read_session_file(key)
        if payload is None or payload.get("key") != key:
            return _json_response({"error": "session not found"}, status=404)
        return _json_response(payload)

    m = re.match(r"^/admin/v1/sessions/([^/]+)$", path)
    if method == "DELETE" and m:
        key = _decode_session_key(m.group(1), ctx)
        if key is None:
            return _json_response({"error": "invalid session key"}, status=400)
        payload = ctx.session_manager.read_session_file(key)
        if payload is None or payload.get("key") != key:
            return _json_response({"deleted": False})
        return _json_response({"deleted": ctx.session_manager.delete_session(key)})

    if method == "GET" and path == "/admin/v1/config":
        return _json_response(_get_config_payload(ctx))

    if method == "PUT" and path == "/admin/v1/config":
        payload, status = _put_config(ctx, body)
        return _json_response(payload, status=status)

    if method == "GET" and path == "/admin/v1/subagents":
        return _json_response(_subagents_payload(ctx))

    m = re.match(r"^/admin/v1/subagents/([^/]+)$", path)
    if method == "GET" and m:
        payload, status = _read_subagent_payload(ctx, m.group(1))
        return _json_response(payload, status=status)

    if method == "PUT" and m:
        payload, status = _write_subagent(ctx, m.group(1), body)
        return _json_response(payload, status=status)

    if method == "DELETE" and m:
        payload, status = _delete_subagent(ctx, m.group(1))
        return _json_response(payload, status=status)

    if method == "GET" and path == "/admin/v1/usage":
        return _json_response(_usage_payload(ctx, parsed.query))

    if method == "GET" and path == "/admin/v1/logs":
        return _json_response(_logs_payload(ctx))

    m = re.match(r"^/admin/v1/logs/([^/]+)$", path)
    if method == "GET" and m:
        payload, status = _tail_log_payload(ctx, m.group(1), parsed.query)
        return _json_response(payload, status=status)

    return _json_response({"error": "Not Found"}, status=404)


async def serve_gateway_http(
    host: str,
    port: int,
    ctx: AdminContext,
    *,
    report: Callable[[str], None] | None = None,
) -> None:
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            raw = await _read_http_header(reader, timeout_s=ctx.config.gateway.admin.request_timeout_s)
            writer.write(await handle_http_request(raw, ctx))
            await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(handle, host, port)
    if report is not None:
        report(f"Health endpoint: http://{host}:{port}/health")
        if ctx.config.gateway.admin.enabled:
            report(f"Admin API: http://{host}:{port}/admin/v1/status")
    async with server:
        await server.serve_forever()
