"""Coordination backends for idempotent execution streams.

One SSE client owns the run and executes the DAG. Concurrent/reconnecting
clients wait for a completion signal and replay the persisted final state. The
in-memory backend is enough for a single process; the Redis backend uses a
`SET NX EX` lock plus pub/sub so the guarantee holds across workers.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.domain.interfaces.services import ExecutionLimiter, StreamCoordinator


class InMemoryExecutionLimiter(ExecutionLimiter):
    """Process-local semaphore for pipeline executions."""

    def __init__(self, max_parallel: int) -> None:
        self._semaphore = asyncio.Semaphore(max(1, int(max_parallel)))
        self._holders: set[str] = set()

    async def acquire(self, owner_id: str) -> None:
        await self._semaphore.acquire()
        self._holders.add(owner_id)

    async def release(self, owner_id: str) -> None:
        if owner_id in self._holders:
            self._holders.discard(owner_id)
            self._semaphore.release()


class InMemoryStreamCoordinator(StreamCoordinator):
    """Per-process coordinator, default for development and single-worker runs."""

    def __init__(self) -> None:
        self._owners: dict[str, str] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._completed: set[str] = set()

    async def try_acquire(self, execution_id: str, owner_id: str) -> bool:
        if execution_id in self._owners:
            return False
        self._owners[execution_id] = owner_id
        return True

    async def release(self, execution_id: str, owner_id: str) -> None:
        if self._owners.get(execution_id) == owner_id:
            self._owners.pop(execution_id, None)

    async def signal(self, execution_id: str) -> None:
        self._completed.add(execution_id)
        self._events.setdefault(execution_id, asyncio.Event()).set()

    async def wait(self, execution_id: str, timeout: float) -> bool:
        event = self._events.setdefault(execution_id, asyncio.Event())
        if execution_id in self._completed or event.is_set():
            return True
        try:
            await asyncio.wait_for(event.wait(), timeout)
            return True
        except asyncio.TimeoutError:
            return False


# Shared default so every module in the process sees the same owners/events.
memory_stream_coordinator = InMemoryStreamCoordinator()


_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class RedisStreamCoordinator(StreamCoordinator):
    """Cross-process coordinator backed by a Redis lock and a pub/sub channel.

    If Redis becomes unreachable the coordinator degrades to the in-memory
    implementation for the rest of the process lifetime, keeping the API alive.
    """

    def __init__(
        self,
        redis_url: str,
        *,
        lock_ttl_seconds: int = 600,
        wait_timeout_seconds: float = 30.0,
    ) -> None:
        self._redis_url = redis_url
        self._lock_ttl = max(1, int(lock_ttl_seconds))
        self._wait_timeout = max(0.1, float(wait_timeout_seconds))
        self._client: Any | None = None
        self._fallback = InMemoryStreamCoordinator()
        self._degraded = False

    def _lock_key(self, execution_id: str) -> str:
        return f"rag-studio:stream:{execution_id}:lock"

    def _done_key(self, execution_id: str) -> str:
        return f"rag-studio:stream:{execution_id}:done"

    def _channel(self, execution_id: str) -> str:
        return f"rag-studio:stream:{execution_id}"

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as redis_asyncio

            self._client = redis_asyncio.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def try_acquire(self, execution_id: str, owner_id: str) -> bool:
        if self._degraded:
            return await self._fallback.try_acquire(execution_id, owner_id)
        try:
            client = await self._get_client()
            acquired = await client.set(
                self._lock_key(execution_id), owner_id, nx=True, ex=self._lock_ttl
            )
            return bool(acquired)
        except Exception:
            self._degraded = True
            return await self._fallback.try_acquire(execution_id, owner_id)

    async def release(self, execution_id: str, owner_id: str) -> None:
        if self._degraded:
            await self._fallback.release(execution_id, owner_id)
            return
        try:
            client = await self._get_client()
            # Compare-and-delete: never remove a lock taken over by another owner.
            await client.eval(_RELEASE_SCRIPT, 1, self._lock_key(execution_id), owner_id)
        except Exception:
            self._degraded = True
            await self._fallback.release(execution_id, owner_id)

    async def signal(self, execution_id: str) -> None:
        if self._degraded:
            await self._fallback.signal(execution_id)
            return
        try:
            client = await self._get_client()
            # Marker checked after subscribing so late clients never miss the signal.
            await client.set(self._done_key(execution_id), "1", ex=self._lock_ttl)
            await client.publish(self._channel(execution_id), "done")
        except Exception:
            self._degraded = True
            await self._fallback.signal(execution_id)

    @staticmethod
    async def _listen(pubsub) -> bool:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                return True
        return False

    async def wait(self, execution_id: str, timeout: float) -> bool:
        if self._degraded:
            return await self._fallback.wait(execution_id, timeout)
        try:
            client = await self._get_client()
            if await client.exists(self._done_key(execution_id)):
                return True
            pubsub = client.pubsub()
            await pubsub.subscribe(self._channel(execution_id))
            try:
                if await client.exists(self._done_key(execution_id)):
                    return True
                return await asyncio.wait_for(self._listen(pubsub), timeout)
            finally:
                await pubsub.close()
        except asyncio.TimeoutError:
            return False
        except Exception:
            self._degraded = True
            return await self._fallback.wait(execution_id, timeout)


_ACQUIRE_SLOT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local owner = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - ttl)
if redis.call('ZSCORE', key, owner) then
    redis.call('ZADD', key, now, owner)
    return 1
end
if redis.call('ZCARD', key) < limit then
    redis.call('ZADD', key, now, owner)
    return 1
end
return 0
"""

_RELEASE_SLOT_SCRIPT = "return redis.call('ZREM', KEYS[1], ARGV[1])"


class RedisExecutionLimiter(ExecutionLimiter):
    """Distributed execution-slot limiter using a Redis sorted set with TTL.

    Stale slots (crashed workers) are purged by score before each acquire, so a
    slot is never lost permanently. Degrades to the in-memory limiter if Redis
    becomes unreachable.
    """

    def __init__(
        self,
        redis_url: str,
        *,
        max_parallel: int = 2,
        slot_ttl_seconds: int = 600,
        poll_interval_seconds: float = 0.05,
    ) -> None:
        self._redis_url = redis_url
        self._max_parallel = max(1, int(max_parallel))
        self._slot_ttl = max(1, int(slot_ttl_seconds))
        self._poll = max(0.01, float(poll_interval_seconds))
        self._key = "rag-studio:execution-slots"
        self._client: Any | None = None
        self._fallback = InMemoryExecutionLimiter(self._max_parallel)
        self._degraded = False

    async def _get_client(self):
        if self._client is None:
            import redis.asyncio as redis_asyncio

            self._client = redis_asyncio.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def acquire(self, owner_id: str) -> None:
        if self._degraded:
            await self._fallback.acquire(owner_id)
            return
        try:
            client = await self._get_client()
            while True:
                granted = await client.eval(
                    _ACQUIRE_SLOT_SCRIPT,
                    1,
                    self._key,
                    time.time(),
                    self._slot_ttl,
                    self._max_parallel,
                    owner_id,
                )
                if granted:
                    return
                await asyncio.sleep(self._poll)
        except Exception:
            self._degraded = True
            await self._fallback.acquire(owner_id)

    async def release(self, owner_id: str) -> None:
        if self._degraded:
            await self._fallback.release(owner_id)
            return
        try:
            client = await self._get_client()
            await client.eval(_RELEASE_SLOT_SCRIPT, 1, self._key, owner_id)
        except Exception:
            self._degraded = True
            await self._fallback.release(owner_id)
