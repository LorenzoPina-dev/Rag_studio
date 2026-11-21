"""Tests for idempotent, multi-worker-safe execution streaming."""

from __future__ import annotations

import asyncio
import copy
import time
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import app.application.execution_stream as stream_module
from app.core.bootstrap import container
from app.domain.interfaces.services import StreamCoordinator
from app.infrastructure.coordination import (
    InMemoryExecutionLimiter,
    InMemoryStreamCoordinator,
    RedisExecutionLimiter,
    RedisStreamCoordinator,
)
from app.infrastructure.memory import store
from app.main import app


def test_stream_reconnect_replays_final_state_without_reexecuting():
    with TestClient(app) as client:
        created = client.post("/api/v1/pipelines/pl_hybrid_rag/run", json={"query": "reconnect"})
        assert created.status_code == 200
        execution_id = created.json()["id"]

        first = client.get(f"/api/v1/executions/{execution_id}/stream")
        assert '"type": "done"' in first.text
        events_before = client.get(f"/api/v1/executions/{execution_id}/events").json()
        starts_before = sum(
            1 for event in events_before if event.get("type") == "execution_started"
        )

        second = client.get(f"/api/v1/executions/{execution_id}/stream")
        assert '"type": "done"' in second.text
        assert '"status": "completed"' in second.text

        events_after = client.get(f"/api/v1/executions/{execution_id}/events").json()
        starts_after = sum(
            1 for event in events_after if event.get("type") == "execution_started"
        )
        assert starts_before == starts_after == 1


@pytest.mark.asyncio
async def test_in_memory_coordinator_is_exclusive_and_owner_scoped():
    coordinator = InMemoryStreamCoordinator()

    assert await coordinator.try_acquire("run_1", "owner-a") is True
    assert await coordinator.try_acquire("run_1", "owner-b") is False

    waiter = asyncio.create_task(coordinator.wait("run_1", timeout=1.0))
    await asyncio.sleep(0)
    assert waiter.done() is False

    await coordinator.release("run_1", "owner-b")  # wrong owner: no-op
    assert await coordinator.try_acquire("run_1", "owner-b") is False

    await coordinator.signal("run_1")
    assert await waiter is True
    assert await coordinator.wait("run_1", timeout=0.01) is True  # late client

    await coordinator.release("run_1", "owner-a")
    assert await coordinator.try_acquire("run_1", "owner-b") is True


@pytest.mark.asyncio
async def test_in_memory_coordinator_wait_can_time_out():
    coordinator = InMemoryStreamCoordinator()
    assert await coordinator.wait("never-signaled", timeout=0.01) is False


class _FakePubSub:
    def __init__(self, redis: "_FakeRedis") -> None:
        self._redis = redis
        self._queue: asyncio.Queue = asyncio.Queue()
        self._channels: list[str] = []

    async def subscribe(self, channel: str) -> None:
        self._channels.append(channel)
        self._redis.subscribers.setdefault(channel, []).append(self._queue)

    async def listen(self):
        while True:
            yield await self._queue.get()

    async def close(self) -> None:
        for channel in self._channels:
            queues = self._redis.subscribers.get(channel, [])
            if self._queue in queues:
                queues.remove(self._queue)


class _FakeRedis:
    """Minimal async Redis surface used by the coordination backends."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.zsets: dict[str, dict[str, float]] = {}
        self.subscribers: dict[str, list[asyncio.Queue]] = {}

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def exists(self, key: str) -> int:
        return 1 if key in self.values else 0

    async def eval(self, script: str, numkeys: int, key: str, *args) -> int:
        assert "redis.call" in script and numkeys == 1
        if "ZREMRANGEBYSCORE" in script:
            now, ttl, limit, owner = args
            slots = self.zsets.setdefault(key, {})
            for member, score in list(slots.items()):
                if score <= now - ttl:
                    del slots[member]
            if owner in slots:
                slots[owner] = now
                return 1
            if len(slots) < limit:
                slots[owner] = now
                return 1
            return 0
        if "ZREM" in script:
            return 1 if self.zsets.get(key, {}).pop(args[0], None) is not None else 0
        owner = args[0]
        if self.values.get(key) == owner:
            del self.values[key]
            return 1
        return 0

    async def publish(self, channel: str, message: str) -> int:
        for queue in list(self.subscribers.get(channel, [])):
            queue.put_nowait({"type": "message", "data": message})
        return len(self.subscribers.get(channel, []))

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub(self)


@pytest.mark.asyncio
async def test_redis_coordinator_lock_pubsub_and_done_marker(monkeypatch):
    fake = _FakeRedis()
    coordinator = RedisStreamCoordinator(
        "redis://fake", lock_ttl_seconds=10, wait_timeout_seconds=0.5
    )
    monkeypatch.setattr(coordinator, "_get_client", AsyncMock(return_value=fake))

    assert isinstance(coordinator, StreamCoordinator)
    assert await coordinator.try_acquire("run_x", "owner-a") is True
    assert await coordinator.try_acquire("run_x", "owner-b") is False

    waiter = asyncio.create_task(coordinator.wait("run_x", timeout=1.0))
    await asyncio.sleep(0.01)

    await coordinator.release("run_x", "owner-b")  # wrong owner: lock stays
    assert await coordinator.try_acquire("run_x", "owner-b") is False

    await coordinator.release("run_x", "owner-a")
    await coordinator.signal("run_x")
    assert await waiter is True

    assert await coordinator.wait("run_x", timeout=0.01) is True  # done marker
    assert await coordinator.try_acquire("run_x", "owner-c") is True  # lock freed
    assert await coordinator.wait("run_y", timeout=0.01) is False  # pub/sub timeout


@pytest.mark.asyncio
async def test_concurrent_sse_clients_execute_the_run_once(monkeypatch):
    coordinator = InMemoryStreamCoordinator()
    monkeypatch.setattr(container, "stream_coordinator", coordinator)

    execution = copy.deepcopy(store.executions[0])
    execution.id = "run_coordinator_test"
    execution.status = "queued"

    started = asyncio.Event()
    release = asyncio.Event()
    calls: list[str] = []

    async def fake_stream(current):
        calls.append(current.status)
        if current.status in {"completed", "failed", "stopped"}:
            yield stream_module._sse(
                {"type": "done", "status": current.status, "execution": current.model_dump()}
            )
            return
        started.set()
        await release.wait()
        current.status = "completed"
        yield stream_module._sse(
            {"type": "done", "status": "completed", "execution": current.model_dump()}
        )

    monkeypatch.setattr(stream_module, "_stream_execution_events", fake_stream)

    async def collect(generator):
        return [frame async for frame in generator]

    owner_task = asyncio.create_task(collect(stream_module.stream_execution_events(execution)))
    await asyncio.wait_for(started.wait(), timeout=1.0)

    waiter_generator = stream_module.stream_execution_events(execution)
    first_frame = await asyncio.wait_for(waiter_generator.__anext__(), timeout=1.0)
    assert '"type": "status"' in first_frame
    waiter_task = asyncio.create_task(collect(waiter_generator))
    await asyncio.sleep(0)  # let the waiter subscribe before the signal

    release.set()
    owner_frames, waiter_frames = await asyncio.gather(owner_task, waiter_task)

    assert calls == ["queued", "completed"]
    assert any('"type": "done"' in frame for frame in owner_frames)
    assert any('"type": "done"' in frame for frame in waiter_frames)


@pytest.mark.asyncio
async def test_stream_does_not_take_over_when_another_owner_still_holds_the_lock(monkeypatch):
    class _BusyCoordinator(InMemoryStreamCoordinator):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        async def try_acquire(self, execution_id: str, owner_id: str) -> bool:
            self.attempts += 1
            return False

        async def wait(self, execution_id: str, timeout: float) -> bool:
            return False

    coordinator = _BusyCoordinator()
    monkeypatch.setattr(container, "stream_coordinator", coordinator)

    execution = copy.deepcopy(store.executions[0])
    execution.id = "run_busy"
    execution.status = "running"

    async def fail_if_called(current):
        raise AssertionError("waiting stream must not execute the pipeline")
        yield  # pragma: no cover

    monkeypatch.setattr(stream_module, "_stream_execution_events", fail_if_called)

    frames = [frame async for frame in stream_module.stream_execution_events(execution)]

    assert coordinator.attempts == 2
    assert any("reconnect" in frame for frame in frames)
    assert any('"status": "running"' in frame for frame in frames)


@pytest.mark.asyncio
async def test_in_memory_execution_limiter_caps_parallel_runs():
    limiter = InMemoryExecutionLimiter(2)
    await limiter.acquire("a")
    await limiter.acquire("b")

    blocked = asyncio.create_task(limiter.acquire("c"))
    await asyncio.sleep(0)
    assert blocked.done() is False

    await limiter.release("b")
    await asyncio.wait_for(blocked, timeout=0.5)
    await limiter.release("a")
    await limiter.release("c")

    await limiter.release("unknown")  # must not inflate the semaphore
    await asyncio.wait_for(limiter.acquire("d"), timeout=0.5)
    await limiter.release("d")


@pytest.mark.asyncio
async def test_redis_execution_limiter_caps_parallel_runs_and_expires_stale_slots(monkeypatch):
    fake = _FakeRedis()
    limiter = RedisExecutionLimiter(
        "redis://fake",
        max_parallel=1,
        slot_ttl_seconds=10,
        poll_interval_seconds=0.01,
    )
    monkeypatch.setattr(limiter, "_get_client", AsyncMock(return_value=fake))

    await limiter.acquire("a")
    blocked = asyncio.create_task(limiter.acquire("b"))
    await asyncio.sleep(0.03)
    assert blocked.done() is False

    await limiter.release("a")
    await asyncio.wait_for(blocked, timeout=0.5)
    assert set(fake.zsets[limiter._key]) == {"b"}

    fake.zsets[limiter._key]["b"] = time.time() - 30  # simulate a crashed worker
    await asyncio.wait_for(limiter.acquire("c"), timeout=0.5)
    assert set(fake.zsets[limiter._key]) == {"c"}
    await limiter.release("c")
    assert fake.zsets[limiter._key] == {}


@pytest.mark.asyncio
async def test_streams_wait_for_an_execution_slot(monkeypatch):
    monkeypatch.setattr(container, "execution_limiter", InMemoryExecutionLimiter(1))
    monkeypatch.setattr(container, "stream_coordinator", InMemoryStreamCoordinator())

    active = 0
    peak = 0
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_stream(current):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        started.set()
        await release.wait()
        active -= 1
        current.status = "completed"
        yield stream_module._sse(
            {"type": "done", "status": "completed", "execution": current.model_dump()}
        )

    monkeypatch.setattr(stream_module, "_stream_execution_events", fake_stream)

    executions = []
    for execution_id in ("run_slot_1", "run_slot_2"):
        execution = copy.deepcopy(store.executions[0])
        execution.id = execution_id
        execution.status = "queued"
        executions.append(execution)

    async def collect(generator):
        return [frame async for frame in generator]

    tasks = [
        asyncio.create_task(collect(stream_module.stream_execution_events(execution)))
        for execution in executions
    ]
    await asyncio.wait_for(started.wait(), timeout=1.0)
    await asyncio.sleep(0.05)
    assert active == 1  # second stream is still waiting for the only slot

    release.set()
    frames = await asyncio.gather(*tasks)

    assert peak == 1
    assert all(any('"type": "done"' in frame for frame in stream_frames) for stream_frames in frames)
