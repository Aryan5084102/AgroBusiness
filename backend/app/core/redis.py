"""Async Redis client accessor (lazy, single shared connection pool)."""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    """Return the shared async Redis client, creating it on first use."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = Redis.from_url(
            str(settings.redis_url),
            encoding="utf-8",
            decode_responses=True,
        )
    return _client


async def close_redis() -> None:
    """Close the Redis client on application shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
