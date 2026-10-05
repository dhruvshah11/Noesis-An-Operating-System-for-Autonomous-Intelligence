"""
Redis async client wrapper.

Two jobs in Milestone 0:
  1. Rate-limit counters (via ``slowapi``'s Redis backend in the future).
  2. Generic TTL cache layer for expensive operations (embeddings, provider
     responses).

LangGraph checkpointing + task broker (Celery/RQ) will build on top of
this connection in later milestones.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, TypeVar

from redis.asyncio import Redis, from_url

from noesis.config import Settings, get_settings
from noesis.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

log = get_logger(__name__)

T = TypeVar("T")


# Module-level singleton
_CLIENT: Redis | None = None


def get_redis(settings: Settings | None = None) -> Redis:
    """Return the singleton Redis client, creating it lazily."""
    global _CLIENT
    if _CLIENT is None or _CLIENT.connection_pool is None:
        s = settings or get_settings()
        _CLIENT = from_url(s.redis_url, decode_responses=False, socket_connect_timeout=5)
        log.info("redis.connected", url=s.redis_url)
    return _CLIENT


@asynccontextmanager
async def redis_pipeline(transaction: bool = True) -> AsyncIterator[Redis]:
    """Context manager yielding a pipeline; executes on exit."""
    pipe = get_redis().pipeline(transaction=transaction)
    try:
        yield pipe
    finally:
        await pipe.execute()


# ---------------------------------------------------------------------------
# Small TTL-cache utility used by agents/RAG.
# ---------------------------------------------------------------------------


async def cache_get(key: str) -> bytes | None:
    return await get_redis().get(key)


async def cache_set(key: str, value: bytes | str, ttl_seconds: int = 3600) -> None:
    await get_redis().set(key, value, ex=ttl_seconds)


async def cache_delete(*keys: str) -> int:
    if not keys:
        return 0
    return int(await get_redis().delete(*keys))
