"""Unit tests for the in-memory fixed-window rate limiter."""

from __future__ import annotations

import pytest
from app.core.ratelimit import InMemoryRateLimiter, RateLimitExceeded


def test_allows_up_to_limit_then_blocks() -> None:
    limiter = InMemoryRateLimiter()
    for _ in range(3):
        limiter.check("k", limit=3, window_seconds=60)
    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("k", limit=3, window_seconds=60)
    assert exc.value.status_code == 429


def test_separate_keys_are_independent() -> None:
    limiter = InMemoryRateLimiter()
    limiter.check("a", limit=1, window_seconds=60)
    # A different key still has its full allowance.
    limiter.check("b", limit=1, window_seconds=60)
    with pytest.raises(RateLimitExceeded):
        limiter.check("a", limit=1, window_seconds=60)
