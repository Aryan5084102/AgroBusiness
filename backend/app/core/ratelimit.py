"""Lightweight fixed-window rate limiting.

Uses an in-process window store by default (works in tests and single-worker
dev). In production, back this with Redis (INCR + EXPIRE) so limits are shared
across workers — the ``RateLimiter`` interface stays the same.
"""

from __future__ import annotations

import time
from collections import defaultdict

from app.core.exceptions import AppError


class RateLimitExceeded(AppError):
    status_code = 429
    code = "rate_limited"


class InMemoryRateLimiter:
    """Fixed-window counter keyed by an arbitrary string (e.g. ip:endpoint)."""

    def __init__(self) -> None:
        # key -> (window_start_epoch, count)
        self._buckets: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = int(time.time())
        window_start = now - (now % window_seconds)
        start, count = self._buckets[key]
        if start != window_start:
            self._buckets[key] = (window_start, 1)
            return
        if count >= limit:
            raise RateLimitExceeded("Too many requests. Please wait a moment and try again.")
        self._buckets[key] = (window_start, count + 1)


# Process-wide limiter instance (swap for a Redis-backed one in production).
login_rate_limiter = InMemoryRateLimiter()
