"""Built-in slash command handlers."""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import suppress
from dataclasses import dataclass

from nanobot import __version__
from nanobot.bus.events import OutboundMessage
from nanobot.command.router import CommandContext, CommandRouter
from nanobot.utils.helpers import build_status_content
from nanobot.utils.restart import set_restart_notice_to_env
from nanobot.workflows.progress import WorkflowProgressManager
from nanobot.workflows.store import WorkflowStore


@dataclass(frozen=True)
class BuiltinCommandSpec:
    command: str
    title: str
    description: str
    icon: str
    arg_hint: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "command": self.command,
            "title": self.title,
            "description": self.description,
            "icon": self.icon,
            "arg_hint": self.arg_hint,
        }


BUILTIN_COMMAND_SPECS: tuple[BuiltinCommandSpec, ...] = (
    BuiltinCommandSpec("/new", "New chat", "Stop the current task and start a fresh conversation.", "square-pen"),
    BuiltinCommandSpec("/stop", "Stop current task", "Cancel the active agent turn for this chat.", "square"),
    BuiltinCommandSpec("/restart", "Restart nanobot", "Restart the bot process in place.", "rotate-cw"),
    BuiltinCommandSpec("/status", "Show status", "Display runtime, provider, and channel status.", "activity"),
    BuiltinCommandSpec("/model", "Switch model preset", "Show or switch the active model preset.", "brain", "[preset]"),
    BuiltinCommandSpec("/history", "Show conversation history", "Print the last N persisted conversation messages.", "history", "[n]"),
    BuiltinCommandSpec("/help", "Show help", "List available slash commands.", "circle-help"),
    BuiltinCommandSpec("/pairing", "Manage pairing", "List, approve, deny or revoke pairing requests.", "shield", "[list|approve <code>|deny <code>|revoke <user_id>]"),
)


def builtin_command_palette() -> list[dict[str, str]]:
    """Return structured command metadata for UI command palettes."""
    return [spec.as_dict() for spec in BUILTIN_COMMAND_SPECS]


async def cmd_stop(ctx: CommandContext) -> OutboundMessage:
    """Cancel all active tasks and subagents for the session."""
    loop = ctx.loop
    msg = ctx.msg
    if hasattr(loop, "_cancel_active_tasks"):
        total = await loop._cancel_active_tasks(msg.session_key)
    else:
        tasks = [t for t in loop._active_tasks.get(msg.session_key, []) if not t.done()]
        for task in tasks:
            task.cancel()
        subagents = await loop.subagents.cancel_by_session(msg.session_key)
        total = len(tasks) + subagents
    content = f"Stopped {total} task(s)." if total else "No active task to stop."
    # Preserve topic thread context so the reply stays in the correct topic
    metadata = {
        "message_thread_id": msg.metadata.get("message_thread_id"),
        "command_response": True,  # Skip TTS for command responses
    }
    return OutboundMessage(
        channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=metadata
    )


async def cmd_restart(ctx: CommandContext) -> OutboundMessage:
    """Restart the process in-place via os.execv."""
    msg = ctx.msg
    set_restart_notice_to_env(
        channel=msg.channel,
        chat_id=msg.chat_id,
        metadata=dict(msg.metadata or {}),
    )

    async def _do_restart():
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable, "-m", "nanobot"] + sys.argv[1:])

    asyncio.create_task(_do_restart())
    # Preserve topic thread context so the reply stays in the correct topic
    metadata = {
        "message_thread_id": msg.metadata.get("message_thread_id"),
        "command_response": True,  # Skip TTS for command responses
    }
    return OutboundMessage(
        channel=msg.channel, chat_id=msg.chat_id, content="Restarting...", metadata=metadata
    )


async def cmd_status(ctx: CommandContext) -> OutboundMessage:
    """Build an outbound status message for a session."""
    loop = ctx.loop
    session = ctx.session or loop.sessions.get_or_create(ctx.key)
    ctx_est = 0
    with suppress(Exception):
        consolidator = getattr(loop, "consolidator", None) or getattr(loop, "memory_consolidator", None)
        if consolidator is not None:
            ctx_est, _ = consolidator.estimate_session_prompt_tokens(session)
    if ctx_est <= 0:
        ctx_est = loop._last_usage.get("prompt_tokens", 0)
    model_override = loop._model_overrides.get(ctx.key)
    # Preserve topic thread context so the reply stays in the correct topic
    metadata = {"render_as": "text"}
    if (thread_id := ctx.msg.metadata.get("message_thread_id")) is not None:
        metadata["message_thread_id"] = thread_id

    # Fetch web search provider usage (best-effort, never blocks the response)
    search_usage_text: str | None = None
    # Never let usage fetch break /status
    with suppress(Exception):
        from nanobot.utils.searchusage import fetch_search_usage

        web_cfg = getattr(loop, "web_config", None)
        search_cfg = getattr(web_cfg, "search", None) if web_cfg else None
        if search_cfg is not None:
            provider = getattr(search_cfg, "provider", "duckduckgo")
            api_key = getattr(search_cfg, "api_key", "") or None
            usage = await fetch_search_usage(provider=provider, api_key=api_key)
            search_usage_text = usage.format()
    active_tasks = loop._active_tasks.get(ctx.key, [])
    task_count = sum(1 for t in active_tasks if not t.done())
    with suppress(Exception):
        task_count += loop.subagents.get_running_count_by_session(ctx.key)
    provider = getattr(loop, "provider", None)
    generation = getattr(provider, "generation", None)
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content=build_status_content(
            version=__version__,
            model=loop.model,
            start_time=loop._start_time,
            last_usage=loop._last_usage,
            context_window_tokens=loop.context_window_tokens,
            session_msg_count=len(session.get_history(max_messages=0)),
            context_tokens_estimate=ctx_est,
            model_override=model_override,
            search_usage_text=search_usage_text,
            active_task_count=task_count,
            max_completion_tokens=getattr(generation, "max_tokens", 8192),
        ),
        metadata=metadata,
    )


async def cmd_new(ctx: CommandContext) -> OutboundMessage:
    """Stop active task and start a fresh session."""
    loop = ctx.loop
    if hasattr(loop, "_cancel_active_tasks"):
        await loop._cancel_active_tasks(ctx.key)
    else:
        tasks = [t for t in loop._active_tasks.get(ctx.key, []) if not t.done()]
        for task in tasks:
            task.cancel()
        await loop.subagents.cancel_by_session(ctx.key)
    session = ctx.session or loop.sessions.get_or_create(ctx.key)
    snapshot = session.messages[session.last_consolidated :]
    session.clear()
    loop.sessions.save(session)
    loop.sessions.invalidate(session.key)
    if snapshot:
        archive_owner = getattr(loop, "consolidator", None) or getattr(
            loop, "memory_consolidator", None
        )
        archive = getattr(archive_owner, "archive", None) or getattr(
            archive_owner, "archive_messages", None
        )
        if archive is not None:
            loop._schedule_background(archive(snapshot))
    # Preserve topic thread context so the reply stays in the correct topic
    metadata = {
        "message_thread_id": ctx.msg.metadata.get("message_thread_id"),
        "command_response": True,  # Skip TTS for command responses
    }
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content="New session started.",
        metadata=metadata,
    )


async def cmd_dream(ctx: CommandContext) -> OutboundMessage:
    """Manually trigger a Dream consolidation run."""
    import time

    loop = ctx.loop
    msg = ctx.msg

    async def _run_dream():
        t0 = time.monotonic()
        try:
            did_work = await loop.dream.run()
            elapsed = time.monotonic() - t0
            if did_work:
                content = f"Dream completed in {elapsed:.1f}s."
            else:
                content = "Dream: nothing to process."
        except Exception as e:
            elapsed = time.monotonic() - t0
            content = f"Dream failed after {elapsed:.1f}s: {e}"
        await loop.bus.publish_outbound(
            OutboundMessage(
                channel=msg.channel,
                chat_id=msg.chat_id,
                content=content,
            )
        )

    asyncio.create_task(_run_dream())
    return OutboundMessage(
        channel=msg.channel,
        chat_id=msg.chat_id,
        content="Dreaming...",
    )


async def cmd_recall(ctx: CommandContext) -> OutboundMessage:
    """Search prior sessions for related work."""
    from nanobot.session.search import SessionSearchService

    query = ctx.args.strip()
    if not query:
        content = "Usage: `/recall <query>`"
    else:
        service = SessionSearchService(ctx.loop.workspace)
        hits = service.search(query, limit=3, exclude_session_key=ctx.key)
        if not hits:
            content = f'No prior session matches found for "{query}".'
        else:
            lines = [f'## Session recall for "{query}"', ""]
            for hit in hits:
                lines.append(f"- Session: `{hit.session_key}`")
                if hit.last_timestamp:
                    lines.append(f"  Last activity: {hit.last_timestamp}")
                lines.append(f"  Excerpt: {hit.excerpt}")
                lines.append("")
            content = "\n".join(lines).rstrip()
    metadata = {"render_as": "text"}
    if (thread_id := ctx.msg.metadata.get("message_thread_id")) is not None:
        metadata["message_thread_id"] = thread_id
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content=content,
        metadata=metadata,
    )


def _workflow_usage() -> str:
    return "Usage: `/workflow list|show <name>|run <name>|step <name>|next|abort`"


def _workflow_progress(ctx: CommandContext) -> WorkflowProgressManager:
    progress = getattr(ctx.loop, "_workflow_progress", None)
    if progress is None:
        progress = WorkflowProgressManager(WorkflowStore(ctx.loop.workspace))
        setattr(ctx.loop, "_workflow_progress", progress)
    return progress


def _workflow_response(ctx: CommandContext, content: str) -> OutboundMessage:
    metadata = {
        "render_as": "text",
        "message_thread_id": ctx.msg.metadata.get("message_thread_id"),
        "command_response": True,
    }
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content=content,
        metadata=metadata,
    )


def _format_workflow_list(ctx: CommandContext) -> str:
    listing = WorkflowStore(ctx.loop.workspace).list()
    lines = ["Workflows:"]
    if listing.workflows:
        for workflow in listing.workflows:
            lines.append(f"- {workflow.name}: {workflow.description} ({workflow.step_count} steps)")
    else:
        lines.append("- No valid workflows found.")

    if listing.invalid:
        lines.extend(["", "Invalid workflows:"])
        for invalid in listing.invalid:
            lines.append(f"- {invalid.name}: {invalid.error}")

    if listing.hint:
        lines.extend(["", listing.hint])
    return "\n".join(lines)


async def cmd_workflow(ctx: CommandContext) -> OutboundMessage:
    """Render instruction-only workflow commands without executing content."""
    args = ctx.args.strip()
    if not args:
        return _workflow_response(ctx, _workflow_usage())

    parts = args.split(maxsplit=1)
    subcommand = parts[0].lower()
    name = parts[1].strip() if len(parts) > 1 else ""
    store = WorkflowStore(ctx.loop.workspace)

    if subcommand == "list":
        return _workflow_response(ctx, _format_workflow_list(ctx))

    if subcommand in {"show", "run"}:
        if not name:
            return _workflow_response(ctx, _workflow_usage())
        workflow, error = store.read(name)
        content = error if error is not None or workflow is None else store.render_full(workflow)
        return _workflow_response(ctx, content or "Unable to read workflow")

    if subcommand == "step":
        if not name:
            return _workflow_response(ctx, _workflow_usage())
        result = _workflow_progress(ctx).start(ctx.key, name)
        return _workflow_response(ctx, result.output)

    if subcommand == "next":
        result = _workflow_progress(ctx).next(ctx.key)
        return _workflow_response(ctx, result.output)

    if subcommand == "abort":
        result = _workflow_progress(ctx).abort(ctx.key)
        return _workflow_response(ctx, result.output)

    return _workflow_response(ctx, _workflow_usage())


def _extract_changed_files(diff: str) -> list[str]:
    """Extract changed file paths from a unified diff."""
    files: list[str] = []
    seen: set[str] = set()
    for line in diff.splitlines():
        if not line.startswith("diff --git "):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        path = parts[3]
        if path.startswith("b/"):
            path = path[2:]
        if path in seen:
            continue
        seen.add(path)
        files.append(path)
    return files


def _format_changed_files(diff: str) -> str:
    files = _extract_changed_files(diff)
    if not files:
        return "No tracked memory files changed."
    return ", ".join(f"`{path}`" for path in files)


def _format_dream_log_content(commit, diff: str, *, requested_sha: str | None = None) -> str:
    files_line = _format_changed_files(diff)
    lines = [
        "## Dream Update",
        "",
        "Here is the selected Dream memory change."
        if requested_sha
        else "Here is the latest Dream memory change.",
        "",
        f"- Commit: `{commit.sha}`",
        f"- Time: {commit.timestamp}",
        f"- Changed files: {files_line}",
    ]
    if diff:
        lines.extend(
            [
                "",
                f"Use `/dream-restore {commit.sha}` to undo this change.",
                "",
                "```diff",
                diff.rstrip(),
                "```",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "Dream recorded this version, but there is no file diff to display.",
            ]
        )
    return "\n".join(lines)


def _format_dream_restore_list(commits: list) -> str:
    lines = [
        "## Dream Restore",
        "",
        "Choose a Dream memory version to restore. Latest first:",
        "",
    ]
    for c in commits:
        lines.append(f"- `{c.sha}` {c.timestamp} - {c.message.splitlines()[0]}")
    lines.extend(
        [
            "",
            "Preview a version with `/dream-log <sha>` before restoring it.",
            "Restore a version with `/dream-restore <sha>`.",
        ]
    )
    return "\n".join(lines)


async def cmd_dream_log(ctx: CommandContext) -> OutboundMessage:
    """Show what the last Dream changed.

    Default: diff of the latest commit (HEAD~1 vs HEAD).
    With /dream-log <sha>: diff of that specific commit.
    """
    store = ctx.loop.consolidator.store
    git = store.git

    if not git.is_initialized():
        if store.get_last_dream_cursor() == 0:
            msg = "Dream has not run yet. Run `/dream`, or wait for the next scheduled Dream cycle."
        else:
            msg = "Dream history is not available because memory versioning is not initialized."
        return OutboundMessage(
            channel=ctx.msg.channel,
            chat_id=ctx.msg.chat_id,
            content=msg,
            metadata={"render_as": "text"},
        )

    args = ctx.args.strip()

    if args:
        # Show diff of a specific commit
        sha = args.split()[0]
        result = git.show_commit_diff(sha)
        if not result:
            content = (
                f"Couldn't find Dream change `{sha}`.\n\n"
                "Use `/dream-restore` to list recent versions, "
                "or `/dream-log` to inspect the latest one."
            )
        else:
            commit, diff = result
            content = _format_dream_log_content(commit, diff, requested_sha=sha)
    else:
        # Default: show the latest commit's diff
        commits = git.log(max_entries=1)
        result = git.show_commit_diff(commits[0].sha) if commits else None
        if result:
            commit, diff = result
            content = _format_dream_log_content(commit, diff)
        else:
            content = "Dream memory has no saved versions yet."

    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content=content,
        metadata={"render_as": "text"},
    )


async def cmd_dream_restore(ctx: CommandContext) -> OutboundMessage:
    """Restore memory files from a previous dream commit.

    Usage:
        /dream-restore          — list recent commits
        /dream-restore <sha>    — revert a specific commit
    """
    store = ctx.loop.consolidator.store
    git = store.git
    if not git.is_initialized():
        return OutboundMessage(
            channel=ctx.msg.channel,
            chat_id=ctx.msg.chat_id,
            content="Dream history is not available because memory versioning is not initialized.",
        )

    args = ctx.args.strip()
    if not args:
        # Show recent commits for the user to pick
        commits = git.log(max_entries=10)
        if not commits:
            content = "Dream memory has no saved versions to restore yet."
        else:
            content = _format_dream_restore_list(commits)
    else:
        sha = args.split()[0]
        result = git.show_commit_diff(sha)
        changed_files = _format_changed_files(result[1]) if result else "the tracked memory files"
        new_sha = git.revert(sha)
        if new_sha:
            content = (
                f"Restored Dream memory to the state before `{sha}`.\n\n"
                f"- New safety commit: `{new_sha}`\n"
                f"- Restored files: {changed_files}\n\n"
                f"Use `/dream-log {new_sha}` to inspect the restore diff."
            )
        else:
            content = (
                f"Couldn't restore Dream change `{sha}`.\n\n"
                "It may not exist, or it may be the first saved version with no earlier state to restore."
            )
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content=content,
        metadata={"render_as": "text"},
    )


_HISTORY_DEFAULT_COUNT = 10
_HISTORY_MAX_COUNT = 50
_HISTORY_MAX_CONTENT_CHARS = 200


def _format_history_message(msg: dict) -> str | None:
    """Format a single history message for display. Returns None to skip."""
    role = msg.get("role")
    if role not in ("user", "assistant"):
        return None
    content = msg.get("content") or ""
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        content = " ".join(parts)
    content = str(content).strip()
    if not content:
        return None
    if len(content) > _HISTORY_MAX_CONTENT_CHARS:
        content = content[:_HISTORY_MAX_CONTENT_CHARS] + "…"
    label = "👤 You" if role == "user" else "🤖 Bot"
    return f"{label}: {content}"


async def cmd_history(ctx: CommandContext) -> OutboundMessage:
    """Show the last N messages of the current session (default 10, max 50).

    Usage: /history [count]
    """
    count = _HISTORY_DEFAULT_COUNT
    if ctx.args.strip():
        try:
            count = max(1, min(int(ctx.args.strip()), _HISTORY_MAX_COUNT))
        except ValueError:
            return OutboundMessage(
                channel=ctx.msg.channel, chat_id=ctx.msg.chat_id,
                content="Usage: /history [count] — e.g. /history 5 (default: 10, max: 50)",
                metadata=dict(ctx.msg.metadata or {}),
            )

    session = ctx.session or ctx.loop.sessions.get_or_create(ctx.key)
    history = session.get_history(max_messages=0)
    visible = [_format_history_message(m) for m in history]
    visible = [m for m in visible if m is not None]
    recent = visible[-count:]

    if not recent:
        return OutboundMessage(
            channel=ctx.msg.channel, chat_id=ctx.msg.chat_id,
            content="No conversation history yet.",
            metadata=dict(ctx.msg.metadata or {}),
        )

    header = f"Last {len(recent)} message(s):\n"
    return OutboundMessage(
        channel=ctx.msg.channel, chat_id=ctx.msg.chat_id,
        content=header + "\n".join(recent),
        metadata={**dict(ctx.msg.metadata or {}), "render_as": "text"},
    )


async def cmd_help(ctx: CommandContext) -> OutboundMessage:
    """Return available slash commands."""
    lines = [
        "🐈 nanobot commands:",
        "/new — Start a new conversation",
        "/stop — Stop the current task",
        "/restart — Restart the bot",
        "/status — Show bot status",
        "/dream — Manually trigger Dream consolidation",
        "/dream-log — Show what the last Dream changed",
        "/dream-restore — Revert memory to a previous state",
        "/recall <query> — Search prior session history",
        "/workflow list — List instruction-only workflows",
        "/workflow show <name> — Show a workflow",
        "/workflow run <name> — Show a workflow checklist",
        "/workflow step <name> — Start step-by-step workflow mode",
        "/workflow next — Show the next workflow step",
        "/workflow abort — Stop step-by-step workflow mode",
        "/model — Show current model",
        "/model <model-id> — Switch model for this session",
        "/model temp — Show temperature settings",
        "/model temp <value> — Set temperature (0.0-2.0)",
        "/help — Show available commands",
    ]
    # Preserve topic thread context so the reply stays in the correct topic
    metadata = {
        "render_as": "text",
        "message_thread_id": ctx.msg.metadata.get("message_thread_id"),
        "command_response": True,  # Skip TTS for command responses
    }
    return OutboundMessage(
        channel=ctx.msg.channel,
        chat_id=ctx.msg.chat_id,
        content="\n".join(lines),
        metadata=metadata,
    )


async def cmd_model(ctx: CommandContext) -> OutboundMessage:
    """Delegate /model handling to the agent loop."""
    return ctx.loop._handle_model_command(ctx.msg, ctx.key, ctx.raw)


def build_help_text() -> str:
    """Build canonical help text shared across channels."""
    lines = [
        "🐈 nanobot commands:",
        "/new — Stop current task and start a new conversation",
        "/stop — Stop the current task",
        "/restart — Restart the bot",
        "/status — Show bot status",
        "/history [n] — Show the last N conversation messages (default 10)",
        "/dream — Manually trigger Dream consolidation",
        "/dream-log — Show what the last Dream changed",
        "/dream-restore — Revert memory to a previous state",
        "/recall <query> — Search prior session history",
        "/workflow list — List instruction-only workflows",
        "/workflow show <name> — Show a workflow",
        "/workflow run <name> — Show a workflow checklist",
        "/workflow step <name> — Start step-by-step workflow mode",
        "/workflow next — Show the next workflow step",
        "/workflow abort — Stop step-by-step workflow mode",
        "/model — Show current model",
        "/model <model-id> — Switch model for this session",
        "/model temp — Show temperature settings",
        "/model temp <value> — Set temperature (0.0-2.0)",
        "/help — Show available commands",
    ]
    return "\n".join(lines)


def register_builtin_commands(router: CommandRouter) -> None:
    """Register the default set of slash commands."""
    router.priority("/stop", cmd_stop)
    router.priority("/restart", cmd_restart)
    router.priority("/status", cmd_status)
    router.exact("/new", cmd_new)
    router.exact("/history", cmd_history)
    router.prefix("/history ", cmd_history)
    router.exact("/dream", cmd_dream)
    router.exact("/dream-log", cmd_dream_log)
    router.prefix("/dream-log ", cmd_dream_log)
    router.exact("/dream-restore", cmd_dream_restore)
    router.prefix("/dream-restore ", cmd_dream_restore)
    router.exact("/recall", cmd_recall)
    router.prefix("/recall ", cmd_recall)
    router.exact("/workflow", cmd_workflow)
    router.prefix("/workflow ", cmd_workflow)
    router.exact("/model", cmd_model)
    router.exact("/status", cmd_status)
    router.exact("/help", cmd_help)
    router.prefix("/model ", cmd_model)
