"""
Gateway Infrastructure — Redis Sliding-Window Rate Limiter

Architectural Intent:
- Implements RateLimiterPort using Redis sorted sets for sliding-window counting
- Each request is scored by its timestamp; expired entries are pruned on read
- Supports both Redis (production) and an in-memory fallback (testing/dev)
- Atomic operations via Lua scripting prevent race conditions under concurrency
"""

from __future__ import annotations

import logging
import time
from typing import Any

from prism.gateway.domain.value_objects.api_types import RateLimitConfig

logger = logging.getLogger(__name__)

# Lua script for atomic sliding-window rate check + record.
# KEYS[1] = rate limit key, ARGV[1] = window_start, ARGV[2] = now, ARGV[3] = limit
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, now .. '-' .. math.random(1000000))
    redis.call('EXPIRE', key, ARGV[4])
    return 1
else
    return 0
end
"""


class RedisRateLimiter:
    """
    Sliding-window rate limiter backed by Redis sorted sets.

    Implements ``RateLimiterPort`` for use in the authentication middleware.

    Each API key gets a Redis sorted set keyed by ``rate_limit:{key_id}``.
    Members are request timestamps; the set is pruned on every check to
    remove entries outside the sliding window.
    """

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client
        self._script_sha: str | None = None

    def _rate_key(self, key_id: str) -> str:
        return f"rate_limit:{key_id}"

    async def _ensure_script(self) -> str:
        """Load the Lua script into Redis and cache its SHA."""
        if self._script_sha is None:
            self._script_sha = await self._redis.script_load(
                _SLIDING_WINDOW_LUA
            )
        return self._script_sha

    async def check_rate_limit(
        self, key_id: str, limit_config: RateLimitConfig
    ) -> bool:
        """
        Check whether the request is within the rate limit.

        Returns True if the request is allowed, False if throttled.
        Uses an atomic Lua script to prevent race conditions.
        """
        now = time.time()
        window_start = now - limit_config.window_seconds
        rate_key = self._rate_key(key_id)

        try:
            script_sha = await self._ensure_script()
            result = await self._redis.evalsha(
                script_sha,
                1,
                rate_key,
                str(window_start),
                str(now),
                str(limit_config.requests_per_minute),
                str(limit_config.window_seconds * 2),
            )
            return bool(result)
        except Exception:
            logger.exception(
                "Rate limiter error for key_id=%s; allowing request", key_id
            )
            # Fail open — do not block requests if rate limiter is unavailable
            return True

    async def record_request(self, key_id: str) -> None:
        """
        Record a request against the given key.

        In the Redis implementation, recording is done atomically within
        ``check_rate_limit``, so this is a no-op. It exists to satisfy
        the ``RateLimiterPort`` protocol for adapters that separate
        checking from recording.
        """
        pass


class InMemoryRateLimiter:
    """
    In-memory sliding-window rate limiter for testing and development.

    Not suitable for production — does not support distributed deployments.
    Implements the same ``RateLimiterPort`` protocol as ``RedisRateLimiter``.
    """

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}

    async def check_rate_limit(
        self, key_id: str, limit_config: RateLimitConfig
    ) -> bool:
        now = time.time()
        window_start = now - limit_config.window_seconds

        if key_id not in self._requests:
            self._requests[key_id] = []

        # Prune expired entries
        self._requests[key_id] = [
            ts for ts in self._requests[key_id] if ts > window_start
        ]

        if len(self._requests[key_id]) >= limit_config.requests_per_minute:
            return False

        return True

    async def record_request(self, key_id: str) -> None:
        now = time.time()
        if key_id not in self._requests:
            self._requests[key_id] = []
        self._requests[key_id].append(now)

    def reset(self) -> None:
        """Clear all recorded requests (for testing)."""
        self._requests.clear()
