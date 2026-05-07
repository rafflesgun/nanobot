import json
from pathlib import Path

from nanobot.admin import server as admin_server
from nanobot.admin.server import (
    AdminContext,
    _read_http_header,
    handle_http_request,
    serve_gateway_http,
)
from nanobot.config.schema import Config
from nanobot.session.manager import Session, SessionManager


def _decode_response(raw: bytes) -> tuple[int, dict]:
    head, body = raw.split(b"\r\n\r\n", 1)
    status = int(head.split(b" ", 2)[1])
    return status, json.loads(body.decode("utf-8"))


def _context(tmp_path: Path, *, enabled: bool = True, token: str = "secret") -> AdminContext:
    cfg = Config.model_validate({
        "agents": {"defaults": {"workspace": str(tmp_path / "workspace"), "model": "test/model"}},
        "gateway": {"admin": {"enabled": enabled, "token": token}},
    })
    return AdminContext(
        config=cfg,
        session_manager=SessionManager(cfg.workspace_path),
        enabled_channels=["websocket"],
        start_time=100.0,
    )


class _FragmentedReader:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    async def read(self, _: int) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


async def test_read_http_header_waits_for_fragmented_headers():
    reader = _FragmentedReader([
        b"GET /health HTTP/1.1\r\n",
        b"Host: x\r\n\r\n",
    ])

    raw = await _read_http_header(reader, timeout_s=1.0)

    assert raw == b"GET /health HTTP/1.1\r\nHost: x\r\n\r\n"


async def test_read_http_header_reads_fragmented_content_length_body():
    body = b'{"model":"new/model"}'
    reader = _FragmentedReader([
        b"PATCH /admin/v1/settings HTTP/1.1\r\n",
        b"Host: x\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n",
        body[:8],
        body[8:],
    ])

    raw = await _read_http_header(reader, timeout_s=1.0)

    assert raw.endswith(body)
    assert raw.split(b"\r\n\r\n", 1)[1] == body


async def test_health_stays_public(tmp_path, monkeypatch):
    monkeypatch.setattr("nanobot.admin.server.time.monotonic", lambda: 130.0)
    raw = await handle_http_request(b"GET /health HTTP/1.1\r\nHost: x\r\n\r\n", _context(tmp_path))

    status, payload = _decode_response(raw)
    assert status == 200
    assert payload == {"status": "ok"}


async def test_non_admin_unknown_path_preserves_plaintext_not_found(tmp_path):
    raw = await handle_http_request(b"GET /missing HTTP/1.1\r\nHost: x\r\n\r\n", _context(tmp_path))

    head, body = raw.split(b"\r\n\r\n", 1)
    assert head.startswith(b"HTTP/1.0 404 Not Found")
    assert b"Content-Type: text/plain" in head
    assert body == b"Not Found"


async def test_serve_gateway_http_reports_endpoints_after_bind(tmp_path, monkeypatch):
    reported: list[str] = []

    class _Server:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            return False

        async def serve_forever(self) -> None:
            reported.append("served")

    async def _start_server(_handler, _host, _port):
        assert reported == []
        reported.append("bound")
        return _Server()

    monkeypatch.setattr("nanobot.admin.server.asyncio.start_server", _start_server)

    await serve_gateway_http("127.0.0.1", 1234, _context(tmp_path), report=reported.append)

    assert reported == [
        "bound",
        "Health endpoint: http://127.0.0.1:1234/health",
        "Admin API: http://127.0.0.1:1234/admin/v1/status",
        "served",
    ]


async def test_admin_status_requires_token(tmp_path):
    raw = await handle_http_request(
        b"GET /admin/v1/status HTTP/1.1\r\nHost: x\r\n\r\n",
        _context(tmp_path),
    )

    status, payload = _decode_response(raw)
    assert status == 401
    assert payload["error"] == "Unauthorized"


async def test_admin_status_payload(tmp_path, monkeypatch):
    monkeypatch.setattr("nanobot.admin.server.time.monotonic", lambda: 130.0)
    raw = await handle_http_request(
        b"GET /admin/v1/status HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        _context(tmp_path),
    )

    status, payload = _decode_response(raw)
    assert status == 200
    assert payload["status"] == "ok"
    assert payload["model"] == "test/model"
    assert payload["uptime_s"] == 30.0
    assert payload["channels"] == ["websocket"]
    assert payload["admin_api"] == {"version": "v1"}


async def test_admin_lists_all_sessions_without_paths(tmp_path):
    ctx = _context(tmp_path)
    session = Session("telegram:123")
    session.add_message("user", "hello")
    ctx.session_manager.save(session)

    raw = await handle_http_request(
        b"GET /admin/v1/sessions HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )

    status, payload = _decode_response(raw)
    assert status == 200
    assert payload["sessions"][0]["key"] == "telegram:123"
    assert "path" not in payload["sessions"][0]


async def test_admin_filters_sessions_by_channel(tmp_path):
    ctx = _context(tmp_path)
    first = Session("telegram:123")
    second = Session("websocket:abc")
    ctx.session_manager.save(first)
    ctx.session_manager.save(second)

    raw = await handle_http_request(
        b"GET /admin/v1/sessions?channel=websocket HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )

    status, payload = _decode_response(raw)
    assert status == 200
    assert [s["key"] for s in payload["sessions"]] == ["websocket:abc"]


async def test_admin_reads_and_deletes_session(tmp_path):
    ctx = _context(tmp_path)
    session = Session("telegram:123")
    session.add_message("user", "hello")
    ctx.session_manager.save(session)

    read_raw = await handle_http_request(
        b"GET /admin/v1/sessions/telegram%3A123/messages HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(read_raw)
    assert status == 200
    assert payload["key"] == "telegram:123"
    assert payload["messages"][0]["content"] == "hello"

    delete_raw = await handle_http_request(
        b"DELETE /admin/v1/sessions/telegram%3A123 HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(delete_raw)
    assert status == 200
    assert payload == {"deleted": True}


async def test_admin_reads_and_deletes_session_with_encoded_slash_key(tmp_path):
    ctx = _context(tmp_path)
    session = Session("telegram:abc/def")
    session.add_message("user", "hello slash")
    ctx.session_manager.save(session)

    list_raw = await handle_http_request(
        b"GET /admin/v1/sessions HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(list_raw)
    assert status == 200
    assert payload["sessions"][0]["key"] == "telegram:abc/def"

    read_raw = await handle_http_request(
        b"GET /admin/v1/sessions/telegram%3Aabc%2Fdef/messages HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(read_raw)
    assert status == 200
    assert payload["key"] == "telegram:abc/def"
    assert payload["messages"][0]["content"] == "hello slash"

    delete_raw = await handle_http_request(
        b"DELETE /admin/v1/sessions/telegram%3Aabc%2Fdef HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(delete_raw)
    assert status == 200
    assert payload == {"deleted": True}


async def test_admin_reads_session_with_encoded_at_sign_key(tmp_path):
    ctx = _context(tmp_path)
    session = Session("telegram:user@example.com")
    session.add_message("user", "hello email")
    ctx.session_manager.save(session)

    list_raw = await handle_http_request(
        b"GET /admin/v1/sessions HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(list_raw)
    assert status == 200
    assert payload["sessions"][0]["key"] == "telegram:user@example.com"

    read_raw = await handle_http_request(
        b"GET /admin/v1/sessions/telegram%3Auser%40example.com/messages HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(read_raw)
    assert status == 200
    assert payload["key"] == "telegram:user@example.com"
    assert payload["messages"][0]["content"] == "hello email"


async def test_admin_reads_and_deletes_session_with_dotted_key(tmp_path):
    ctx = _context(tmp_path)
    session = Session("api:foo..bar")
    session.add_message("user", "hello dots")
    ctx.session_manager.save(session)

    list_raw = await handle_http_request(
        b"GET /admin/v1/sessions HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(list_raw)
    assert status == 200
    assert payload["sessions"][0]["key"] == "api:foo..bar"

    read_raw = await handle_http_request(
        b"GET /admin/v1/sessions/api%3Afoo..bar/messages HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(read_raw)
    assert status == 200
    assert payload["key"] == "api:foo..bar"
    assert payload["messages"][0]["content"] == "hello dots"

    delete_raw = await handle_http_request(
        b"DELETE /admin/v1/sessions/api%3Afoo..bar HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(delete_raw)
    assert status == 200
    assert payload == {"deleted": True}


async def test_admin_rejects_colliding_session_key_alias(tmp_path):
    ctx = _context(tmp_path)
    session = Session("telegram:abc/def")
    session.add_message("user", "hello real")
    ctx.session_manager.save(session)

    alias_read_raw = await handle_http_request(
        b"GET /admin/v1/sessions/telegram%3Aabc%3Adef/messages HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, _ = _decode_response(alias_read_raw)
    assert status != 200

    alias_delete_raw = await handle_http_request(
        b"DELETE /admin/v1/sessions/telegram%3Aabc%3Adef HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(alias_delete_raw)
    assert status == 200
    assert payload == {"deleted": False}

    real_read_raw = await handle_http_request(
        b"GET /admin/v1/sessions/telegram%3Aabc%2Fdef/messages HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(real_read_raw)
    assert status == 200
    assert payload["key"] == "telegram:abc/def"
    assert payload["messages"][0]["content"] == "hello real"


async def test_admin_settings_read_and_patch(tmp_path):
    ctx = _context(tmp_path)

    read_raw = await handle_http_request(
        b"GET /admin/v1/settings HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(read_raw)
    assert status == 200
    assert payload["agent"]["model"] == "test/model"

    patch_body = b'{"model":"new/model","provider":"auto"}'
    patch_raw = await handle_http_request(
        b"PATCH /admin/v1/settings HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\nContent-Length: "
        + str(len(patch_body)).encode()
        + b"\r\n\r\n"
        + patch_body,
        ctx,
    )
    status, payload = _decode_response(patch_raw)
    assert status == 200
    assert payload["agent"]["model"] == "new/model"
    assert payload["requires_restart"] is True


async def test_admin_settings_patch_rejects_non_object_json(tmp_path):
    ctx = _context(tmp_path)
    patch_body = b"[]"

    patch_raw = await handle_http_request(
        b"PATCH /admin/v1/settings HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\nContent-Length: "
        + str(len(patch_body)).encode()
        + b"\r\n\r\n"
        + patch_body,
        ctx,
    )
    status, payload = _decode_response(patch_raw)

    assert status == 400
    assert payload == {"error": "json object required"}


async def test_admin_settings_patch_rejects_unknown_provider(tmp_path):
    ctx = _context(tmp_path)
    patch_body = b'{"provider":"missing-provider"}'

    patch_raw = await handle_http_request(
        b"PATCH /admin/v1/settings HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\nContent-Length: "
        + str(len(patch_body)).encode()
        + b"\r\n\r\n"
        + patch_body,
        ctx,
    )
    status, payload = _decode_response(patch_raw)

    assert status == 400
    assert payload == {"error": "unknown provider"}


async def test_admin_settings_patch_rejects_blank_provider(tmp_path):
    ctx = _context(tmp_path)
    patch_body = b'{"provider":"   "}'

    patch_raw = await handle_http_request(
        b"PATCH /admin/v1/settings HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\nContent-Length: "
        + str(len(patch_body)).encode()
        + b"\r\n\r\n"
        + patch_body,
        ctx,
    )
    status, payload = _decode_response(patch_raw)

    assert status == 400
    assert payload == {"error": "provider is required"}


async def test_admin_lists_builtin_and_workspace_subagents(tmp_path):
    ctx = _context(tmp_path)
    agents_dir = ctx.config.workspace_path / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "release-reviewer.md").write_text(
        "---\nname: release-reviewer\ndescription: Reviews releases\nmodel: test/model\ntools:\n  - grep\nmax_iterations: 4\nmax_tokens: 2000\n---\n\nReview releases.",
        encoding="utf-8",
    )

    raw = await handle_http_request(
        b"GET /admin/v1/subagents HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )

    status, payload = _decode_response(raw)
    assert status == 200
    names = {item["name"]: item for item in payload["subagents"]}
    assert names["recall"]["source"] == "builtin"
    assert names["recall"]["editable"] is False
    assert names["release-reviewer"] == {
        "name": "release-reviewer",
        "description": "Reviews releases",
        "model": "test/model",
        "tools": ["grep"],
        "max_iterations": 4,
        "max_tokens": 2000,
        "source": "workspace",
        "editable": True,
    }


async def test_admin_reads_subagent_markdown_without_paths(tmp_path):
    ctx = _context(tmp_path)
    agents_dir = ctx.config.workspace_path / "agents"
    agents_dir.mkdir(parents=True)
    content = "---\nname: ops-triage\ndescription: Triage incidents\nmodel: test/model\n---\n\nInspect logs."
    (agents_dir / "ops-triage.md").write_text(content, encoding="utf-8")

    raw = await handle_http_request(
        b"GET /admin/v1/subagents/ops-triage HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )

    status, payload = _decode_response(raw)
    assert status == 200
    assert payload["name"] == "ops-triage"
    assert payload["content"] == content
    assert payload["source"] == "workspace"
    assert str(ctx.config.workspace_path) not in json.dumps(payload)


async def test_admin_writes_and_deletes_workspace_subagent(tmp_path):
    ctx = _context(tmp_path)
    content = "---\nname: ops-triage\ndescription: Triage incidents\nmodel: test/model\ntools:\n  - grep\n---\n\nInspect logs."
    body = json.dumps({"content": content}).encode("utf-8")

    put_raw = await handle_http_request(
        b"PUT /admin/v1/subagents/ops-triage HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
        + body,
        ctx,
    )
    status, payload = _decode_response(put_raw)
    assert status == 200
    assert payload["subagent"]["name"] == "ops-triage"
    assert (ctx.config.workspace_path / "agents" / "ops-triage.md").read_text(encoding="utf-8") == content

    delete_raw = await handle_http_request(
        b"DELETE /admin/v1/subagents/ops-triage HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(delete_raw)
    assert status == 200
    assert payload == {"deleted": True}
    assert not (ctx.config.workspace_path / "agents" / "ops-triage.md").exists()


async def test_admin_rejects_unsafe_or_readonly_subagent_writes(tmp_path):
    ctx = _context(tmp_path)
    valid_body = json.dumps({"content": "---\nname: recall\ndescription: nope\n---\n\nBody"}).encode("utf-8")

    unsafe_raw = await handle_http_request(
        b"PUT /admin/v1/subagents/..%2Fevil HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\nContent-Length: "
        + str(len(valid_body)).encode()
        + b"\r\n\r\n"
        + valid_body,
        ctx,
    )
    status, payload = _decode_response(unsafe_raw)
    assert status == 400
    assert payload == {"error": "invalid subagent name"}

    builtin_delete_raw = await handle_http_request(
        b"DELETE /admin/v1/subagents/recall HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(builtin_delete_raw)
    assert status == 403
    assert payload == {"error": "read-only subagent"}


async def test_admin_rejects_invalid_subagent_markdown(tmp_path):
    ctx = _context(tmp_path)
    body = json.dumps({"content": "---\nname: other\ntools: grep\n---\n\n"}).encode("utf-8")

    raw = await handle_http_request(
        b"PUT /admin/v1/subagents/ops-triage HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
        + body,
        ctx,
    )

    status, payload = _decode_response(raw)
    assert status == 400
    assert payload["error"] == "subagent name mismatch"


async def test_admin_usage_returns_zero_payload_without_usage_file(tmp_path):
    ctx = _context(tmp_path)

    raw = await handle_http_request(
        b"GET /admin/v1/usage HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )

    status, payload = _decode_response(raw)
    assert status == 200
    assert payload["totals"] == {"count": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
    assert payload["by_day"] == []
    assert payload["by_model"] == []
    assert payload["pricing"] == {"configured": False, "message": "Pricing is not configured; showing token usage only."}


async def test_admin_usage_aggregates_by_day_model_channel_and_session(tmp_path):
    ctx = _context(tmp_path)
    stats_dir = ctx.config.workspace_path / "stats"
    stats_dir.mkdir(parents=True)
    (stats_dir / "usage.jsonl").write_text(
        "\n".join([
            json.dumps({"timestamp": "2026-05-06T10:00:00", "channel": "websocket", "chat_id": "a", "model": "m1", "input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "cached_tokens": 3, "session_key": "websocket:a"}),
            json.dumps({"timestamp": "2026-05-06T11:00:00", "channel": "telegram", "chat_id": "b", "model": "m2", "input_tokens": 20, "output_tokens": 7, "total_tokens": 27, "session_key": "telegram:b"}),
            "not-json",
        ]),
        encoding="utf-8",
    )

    raw = await handle_http_request(
        b"GET /admin/v1/usage?days=not-a-number HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )

    status, payload = _decode_response(raw)
    assert status == 200
    assert payload["range"] == {"days": 30}
    assert payload["totals"] == {"count": 2, "input_tokens": 30, "output_tokens": 12, "total_tokens": 42, "cached_tokens": 3}
    assert payload["by_day"] == [{"key": "2026-05-06", "count": 2, "input_tokens": 30, "output_tokens": 12, "total_tokens": 42, "cached_tokens": 3}]
    assert {row["key"] for row in payload["by_model"]} == {"m1", "m2"}
    assert {row["key"] for row in payload["by_channel"]} == {"websocket", "telegram"}
    assert {row["key"] for row in payload["by_session"]} == {"websocket:a", "telegram:b"}
    assert payload["warnings"] == [{"skipped_lines": 1}]


async def test_admin_usage_filters_by_channel_model_and_session(tmp_path):
    ctx = _context(tmp_path)
    stats_dir = ctx.config.workspace_path / "stats"
    stats_dir.mkdir(parents=True)
    (stats_dir / "usage.jsonl").write_text(
        "\n".join([
            json.dumps({"timestamp": "2026-05-06T10:00:00", "channel": "websocket", "chat_id": "a", "model": "m1", "input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "session_key": "websocket:a"}),
            json.dumps({"timestamp": "2026-05-07T10:00:00", "channel": "telegram", "chat_id": "b", "model": "m2", "input_tokens": 20, "output_tokens": 7, "total_tokens": 27, "session_key": "telegram:b"}),
        ]),
        encoding="utf-8",
    )

    raw = await handle_http_request(
        b"GET /admin/v1/usage?days=999&channel=websocket&model=m1&session_key=websocket%3Aa HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )

    status, payload = _decode_response(raw)
    assert status == 200
    assert payload["range"] == {"days": 366}
    assert payload["totals"]["total_tokens"] == 15
    assert payload["by_channel"] == [{"key": "websocket", "count": 1, "input_tokens": 10, "output_tokens": 5, "total_tokens": 15, "cached_tokens": 0}]


async def test_admin_logs_list_and_tail_are_bounded(tmp_path):
    ctx = _context(tmp_path)
    log_dir = ctx.config.workspace_path / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "nanobot.log").write_text("one\ntwo\nthree\n", encoding="utf-8")

    list_raw = await handle_http_request(
        b"GET /admin/v1/logs HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(list_raw)
    assert status == 200
    assert payload["logs"] == [{"name": "nanobot.log"}]

    tail_raw = await handle_http_request(
        b"GET /admin/v1/logs/nanobot.log?tail=2 HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(tail_raw)
    assert status == 200
    assert payload == {"name": "nanobot.log", "lines": ["two", "three"]}


async def test_admin_log_tail_invalid_value_is_clamped_to_config(tmp_path):
    cfg = Config.model_validate({
        "agents": {"defaults": {"workspace": str(tmp_path / "workspace"), "model": "test/model"}},
        "gateway": {"admin": {"enabled": True, "token": "secret", "maxLogTailLines": 3}},
    })
    ctx = AdminContext(
        config=cfg,
        session_manager=SessionManager(cfg.workspace_path),
        enabled_channels=["websocket"],
        start_time=100.0,
    )
    log_dir = ctx.config.workspace_path / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "nanobot.log").write_text("\n".join(f"line-{i}" for i in range(10)), encoding="utf-8")

    tail_raw = await handle_http_request(
        b"GET /admin/v1/logs/nanobot.log?tail=not-a-number HTTP/1.1\r\nHost: x\r\nAuthorization: Bearer secret\r\n\r\n",
        ctx,
    )
    status, payload = _decode_response(tail_raw)

    assert status == 200
    assert len(payload["lines"]) == 3
    assert payload["lines"] == ["line-7", "line-8", "line-9"]


def test_tail_lines_returns_last_requested_lines(tmp_path):
    path = tmp_path / "large.log"
    path.write_text("\n".join(f"line-{i}" for i in range(2000)) + "\n", encoding="utf-8")

    lines = admin_server._tail_lines(path, 4)

    assert lines == ["line-1996", "line-1997", "line-1998", "line-1999"]


def test_tail_lines_is_byte_bounded_for_huge_single_line(tmp_path):
    path = tmp_path / "huge.log"
    path.write_text("x" * (admin_server._MAX_LOG_TAIL_BYTES + 100_000), encoding="utf-8")

    lines = admin_server._tail_lines(path, 1)

    assert len(lines) == 1
    assert len(lines[0].encode("utf-8")) <= admin_server._MAX_LOG_TAIL_BYTES
