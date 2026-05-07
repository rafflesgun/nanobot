"""Small HTTP surface for gateway health and admin API routes."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlparse

from nanobot.admin.auth import is_authorized
from nanobot.config.schema import Config
from nanobot.providers.registry import find_by_name
from nanobot.session.manager import SessionManager

_MAX_REQUEST_HEADER_BYTES = 65536
_MAX_REQUEST_BODY_BYTES = 1024 * 1024
_MAX_LOG_TAIL_BYTES = 256 * 1024


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


def _settings_payload(ctx: AdminContext, *, requires_restart: bool = False) -> dict[str, Any]:
    model = ctx.config.agents.defaults.model
    return {
        "agent": {
            "model": model,
            "provider": ctx.config.agents.defaults.provider,
            "resolved_provider": ctx.config.get_provider_name(model),
            "has_api_key": bool(ctx.config.get_api_key(model)),
        },
        "requires_restart": requires_restart,
    }


def _patch_settings(ctx: AdminContext, body: bytes) -> tuple[dict[str, Any], int]:
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {"error": "invalid json"}, 400
    if not isinstance(payload, dict):
        return {"error": "json object required"}, 400
    changed = False
    model = payload.get("model")
    if model is not None:
        if not isinstance(model, str) or not model.strip():
            return {"error": "model is required"}, 400
        if ctx.config.agents.defaults.model != model.strip():
            ctx.config.agents.defaults.model = model.strip()
            changed = True
    provider = payload.get("provider")
    if provider is not None:
        if not isinstance(provider, str) or not provider.strip():
            return {"error": "provider is required"}, 400
        provider = provider.strip()
        if provider != "auto" and find_by_name(provider) is None:
            return {"error": "unknown provider"}, 400
        if ctx.config.agents.defaults.provider != provider:
            ctx.config.agents.defaults.provider = provider
            changed = True
    return _settings_payload(ctx, requires_restart=changed), 200


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

    if method == "GET" and path == "/admin/v1/settings":
        return _json_response(_settings_payload(ctx))

    if method == "PATCH" and path == "/admin/v1/settings":
        payload, status = _patch_settings(ctx, body)
        return _json_response(payload, status=status)

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
