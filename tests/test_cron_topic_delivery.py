"""Tests for cron job delivery routing: Topic → Topic, Group → Group, DM → DM."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.agent.tools.context import RequestContext
from nanobot.agent.tools.cron import CronTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.cron.service import CronService
from nanobot.cron.types import CronJob, CronJobState, CronPayload, CronSchedule

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loop(tmp_path: Path, cron_service: CronService | None = None) -> AgentLoop:
    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    return AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        cron_service=cron_service,
    )


def _make_job(
    channel: str,
    to: str,
    thread_id: int | None = None,
) -> CronJob:
    return CronJob(
        id="testjob",
        name="Test Job",
        enabled=True,
        schedule=CronSchedule(kind="every", every_ms=60_000),
        payload=CronPayload(
            kind="agent_turn",
            message="Do the thing",
            deliver=True,
            channel=channel,
            to=to,
            origin_channel=channel,
            origin_chat_id=to,
            thread_id=thread_id,
        ),
        state=CronJobState(),
        created_at_ms=0,
        updated_at_ms=0,
    )


# ---------------------------------------------------------------------------
# CronPayload persistence
# ---------------------------------------------------------------------------

class TestCronPayloadThreadId:
    """thread_id survives serialisation round-trips."""

    def test_add_job_stores_thread_id(self, tmp_path: Path) -> None:
        service = CronService(tmp_path / "cron" / "jobs.json")
        job = service.add_job(
            name="topic reminder",
            schedule=CronSchedule(kind="every", every_ms=60_000),
            message="hello topic",
            deliver=True,
            channel="telegram",
            to="-1001234567890",
            thread_id=42,
        )
        assert job.payload.thread_id == 42

    def test_thread_id_roundtrips_to_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "cron" / "jobs.json"
        svc1 = CronService(path)
        svc1.add_job(
            name="roundtrip",
            schedule=CronSchedule(kind="every", every_ms=60_000),
            message="ping",
            deliver=True,
            channel="telegram",
            to="-100999",
            thread_id=77,
        )

        # Fresh service reads from disk
        svc2 = CronService(path)
        jobs = svc2.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].payload.thread_id == 77

    def test_thread_id_none_roundtrips(self, tmp_path: Path) -> None:
        path = tmp_path / "cron" / "jobs.json"
        svc1 = CronService(path)
        svc1.add_job(
            name="dm job",
            schedule=CronSchedule(kind="every", every_ms=60_000),
            message="dm ping",
            deliver=True,
            channel="telegram",
            to="987654321",
            thread_id=None,
        )

        svc2 = CronService(path)
        jobs = svc2.list_jobs()
        assert jobs[0].payload.thread_id is None


# ---------------------------------------------------------------------------
# CronTool context propagation
# ---------------------------------------------------------------------------

class TestCronToolContext:
    """set_context stores thread_id and passes it through to add_job."""

    def test_set_context_stores_thread_id(self, tmp_path: Path) -> None:
        svc = CronService(tmp_path / "cron" / "jobs.json")
        tool = CronTool(svc)
        ctx = RequestContext(
            channel="telegram", chat_id="-1001234567890",
            thread_id=42, metadata={"message_thread_id": 42},
        )
        tool.set_context(ctx)
        assert tool._thread_id == 42

    def test_set_context_no_thread_id_defaults_none(self, tmp_path: Path) -> None:
        svc = CronService(tmp_path / "cron" / "jobs.json")
        tool = CronTool(svc)
        ctx = RequestContext(
            channel="telegram", chat_id="123456789",
            thread_id=None, metadata={},
        )
        tool.set_context(ctx)
        assert tool._thread_id is None

    @pytest.mark.asyncio
    async def test_add_action_propagates_thread_id(self, tmp_path: Path) -> None:
        svc = CronService(tmp_path / "cron" / "jobs.json")
        tool = CronTool(svc)
        ctx = RequestContext(
            channel="telegram", chat_id="-1001234567890",
            thread_id=99, metadata={"message_thread_id": 99},
            session_key="telegram:-1001234567890:topic:99",
        )
        tool.set_context(ctx)

        result = await tool.execute(
            action="add",
            message="Daily reminder",
            every_seconds=3600,
        )

        assert "Created job" in result
        jobs = svc.list_jobs()
        assert len(jobs) == 1
        assert jobs[0].payload.thread_id == 99
        assert jobs[0].payload.origin_channel == "telegram"
        assert jobs[0].payload.origin_chat_id == "-1001234567890"

    @pytest.mark.asyncio
    async def test_add_action_no_thread_id_stores_none(self, tmp_path: Path) -> None:
        svc = CronService(tmp_path / "cron" / "jobs.json")
        tool = CronTool(svc)
        ctx = RequestContext(
            channel="telegram", chat_id="123456789",
            thread_id=None, metadata={},
            session_key="telegram:123456789",
        )
        tool.set_context(ctx)

        await tool.execute(action="add", message="DM reminder", every_seconds=300)

        jobs = svc.list_jobs()
        assert jobs[0].payload.thread_id is None


# ---------------------------------------------------------------------------
# AgentLoop._set_tool_context → CronTool
# ---------------------------------------------------------------------------

class TestAgentLoopCronContext:
    """AgentLoop forwards message_thread_id from inbound metadata to CronTool."""

    def test_set_tool_context_passes_thread_id_to_cron_tool(self, tmp_path: Path) -> None:
        svc = CronService(tmp_path / "cron" / "jobs.json")
        loop = _make_loop(tmp_path, cron_service=svc)

        loop._set_tool_context(
            channel="telegram",
            chat_id="-1001234567890",
            message_id="55",
            thread_id=42,
        )

        cron_tool = loop.tools.get("cron")
        assert isinstance(cron_tool, CronTool)
        assert cron_tool._channel == "telegram"
        assert cron_tool._chat_id == "-1001234567890"
        assert cron_tool._thread_id == 42

    def test_set_tool_context_no_thread_id(self, tmp_path: Path) -> None:
        svc = CronService(tmp_path / "cron" / "jobs.json")
        loop = _make_loop(tmp_path, cron_service=svc)

        loop._set_tool_context(
            channel="telegram",
            chat_id="987654321",
            message_id=None,
            thread_id=None,
        )

        cron_tool = loop.tools.get("cron")
        assert isinstance(cron_tool, CronTool)
        assert cron_tool._thread_id is None

    @pytest.mark.asyncio
    async def test_inbound_topic_message_sets_cron_thread_id(self, tmp_path: Path) -> None:
        """Processing an inbound Topic message sets CronTool thread_id correctly."""
        from nanobot.providers.base import LLMResponse

        svc = CronService(tmp_path / "cron" / "jobs.json")
        loop = _make_loop(tmp_path, cron_service=svc)
        loop.provider.chat_with_retry = AsyncMock(
            return_value=LLMResponse(content="ok", tool_calls=[])
        )
        loop.tools.get_definitions = MagicMock(return_value=[])

        msg = InboundMessage(
            channel="telegram",
            sender_id="user1",
            chat_id="-1001234567890",
            content="Schedule something",
            metadata={"message_thread_id": 42, "message_id": "10"},
        )
        await loop._process_message(msg)

        cron_tool = loop.tools.get("cron")
        assert isinstance(cron_tool, CronTool)
        assert cron_tool._thread_id == 42


# ---------------------------------------------------------------------------
# Delivery routing: outbound message metadata
# ---------------------------------------------------------------------------

class TestCronDeliveryRouting:
    """OutboundMessage carries message_thread_id iff the job has a thread_id."""

    @pytest.mark.asyncio
    async def test_topic_job_outbound_has_thread_id(self) -> None:
        """Topic job → OutboundMessage must contain message_thread_id."""
        published: list[OutboundMessage] = []

        async def fake_publish(msg: OutboundMessage) -> None:
            published.append(msg)

        job = _make_job(channel="telegram", to="-1001234567890", thread_id=42)

        delivery_meta: dict = {}
        if job.payload.thread_id:
            delivery_meta["message_thread_id"] = job.payload.thread_id

        out = OutboundMessage(
            channel=job.payload.origin_channel or "cli",
            chat_id=job.payload.origin_chat_id,
            content="Reminder result",
            metadata=delivery_meta,
        )
        await fake_publish(out)

        assert len(published) == 1
        assert published[0].metadata.get("message_thread_id") == 42
        assert published[0].chat_id == "-1001234567890"
        assert published[0].channel == "telegram"

    @pytest.mark.asyncio
    async def test_group_job_outbound_has_no_thread_id(self) -> None:
        """Group job (no topic) → OutboundMessage must NOT contain message_thread_id."""
        published: list[OutboundMessage] = []

        async def fake_publish(msg: OutboundMessage) -> None:
            published.append(msg)

        job = _make_job(channel="telegram", to="-1001234567890", thread_id=None)

        delivery_meta: dict = {}
        if job.payload.thread_id:
            delivery_meta["message_thread_id"] = job.payload.thread_id

        out = OutboundMessage(
            channel=job.payload.origin_channel or "cli",
            chat_id=job.payload.origin_chat_id,
            content="Group result",
            metadata=delivery_meta,
        )
        await fake_publish(out)

        assert len(published) == 1
        assert "message_thread_id" not in published[0].metadata
        assert published[0].chat_id == "-1001234567890"

    @pytest.mark.asyncio
    async def test_dm_job_outbound_has_no_thread_id(self) -> None:
        """DM job → OutboundMessage must NOT contain message_thread_id."""
        published: list[OutboundMessage] = []

        async def fake_publish(msg: OutboundMessage) -> None:
            published.append(msg)

        job = _make_job(channel="telegram", to="987654321", thread_id=None)

        delivery_meta: dict = {}
        if job.payload.thread_id:
            delivery_meta["message_thread_id"] = job.payload.thread_id

        out = OutboundMessage(
            channel=job.payload.origin_channel or "cli",
            chat_id=job.payload.origin_chat_id,
            content="DM result",
            metadata=delivery_meta,
        )
        await fake_publish(out)

        assert len(published) == 1
        assert "message_thread_id" not in published[0].metadata
        assert published[0].chat_id == "987654321"
