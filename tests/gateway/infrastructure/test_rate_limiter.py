"""
Tests for Gateway Infrastructure — Rate Limiter

Covers:
- InMemoryRateLimiter sliding-window behaviour
- Requests within limit are allowed
- Requests exceeding limit are rejected
- Window expiry allows new requests
- Reset clears all state
"""

from __future__ import annotations

import pytest

from prism.gateway.domain.value_objects.api_types import RateLimitConfig
from prism.gateway.infrastructure.middleware.rate_limiter import InMemoryRateLimiter


@pytest.fixture
def rate_limiter() -> InMemoryRateLimiter:
    return InMemoryRateLimiter()


@pytest.fixture
def strict_config() -> RateLimitConfig:
    """A strict rate limit: 5 requests per 60-second window."""
    return RateLimitConfig(
        requests_per_minute=5,
        burst_size=10,
        window_seconds=60,
    )


@pytest.fixture
def relaxed_config() -> RateLimitConfig:
    """A relaxed rate limit: 1000 requests per 60-second window."""
    return RateLimitConfig(
        requests_per_minute=1000,
        burst_size=2000,
        window_seconds=60,
    )


class TestInMemoryRateLimiter:
    """Tests for the in-memory rate limiter implementation."""

    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(
        self, rate_limiter: InMemoryRateLimiter, strict_config: RateLimitConfig
    ) -> None:
        key_id = "key-001"

        for _ in range(5):
            allowed = await rate_limiter.check_rate_limit(key_id, strict_config)
            assert allowed is True
            await rate_limiter.record_request(key_id)

    @pytest.mark.asyncio
    async def test_rejects_requests_exceeding_limit(
        self, rate_limiter: InMemoryRateLimiter, strict_config: RateLimitConfig
    ) -> None:
        key_id = "key-002"

        # Fill up the limit
        for _ in range(5):
            await rate_limiter.record_request(key_id)

        # Next request should be rejected
        allowed = await rate_limiter.check_rate_limit(key_id, strict_config)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_different_keys_have_independent_limits(
        self, rate_limiter: InMemoryRateLimiter, strict_config: RateLimitConfig
    ) -> None:
        # Fill up key-A
        for _ in range(5):
            await rate_limiter.record_request("key-A")

        # key-B should still be allowed
        allowed = await rate_limiter.check_rate_limit("key-B", strict_config)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_reset_clears_all_state(
        self, rate_limiter: InMemoryRateLimiter, strict_config: RateLimitConfig
    ) -> None:
        key_id = "key-003"

        # Fill up the limit
        for _ in range(5):
            await rate_limiter.record_request(key_id)

        # Should be throttled
        allowed = await rate_limiter.check_rate_limit(key_id, strict_config)
        assert allowed is False

        # Reset and verify requests are allowed again
        rate_limiter.reset()
        allowed = await rate_limiter.check_rate_limit(key_id, strict_config)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_first_request_always_allowed(
        self, rate_limiter: InMemoryRateLimiter, strict_config: RateLimitConfig
    ) -> None:
        allowed = await rate_limiter.check_rate_limit("new-key", strict_config)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_relaxed_config_allows_many_requests(
        self, rate_limiter: InMemoryRateLimiter, relaxed_config: RateLimitConfig
    ) -> None:
        key_id = "key-relaxed"

        for _ in range(100):
            allowed = await rate_limiter.check_rate_limit(key_id, relaxed_config)
            assert allowed is True
            await rate_limiter.record_request(key_id)


class TestRateLimitConfigValidation:
    """Tests for RateLimitConfig value object validation."""

    def test_valid_config(self) -> None:
        config = RateLimitConfig(
            requests_per_minute=100, burst_size=200, window_seconds=60
        )
        assert config.requests_per_minute == 100
        assert config.burst_size == 200
        assert config.window_seconds == 60

    def test_zero_requests_per_minute_raises(self) -> None:
        with pytest.raises(ValueError, match="requests_per_minute must be positive"):
            RateLimitConfig(requests_per_minute=0, burst_size=10)

    def test_negative_requests_per_minute_raises(self) -> None:
        with pytest.raises(ValueError, match="requests_per_minute must be positive"):
            RateLimitConfig(requests_per_minute=-1, burst_size=10)

    def test_zero_burst_size_raises(self) -> None:
        with pytest.raises(ValueError, match="burst_size must be positive"):
            RateLimitConfig(requests_per_minute=100, burst_size=0)

    def test_zero_window_seconds_raises(self) -> None:
        with pytest.raises(ValueError, match="window_seconds must be positive"):
            RateLimitConfig(
                requests_per_minute=100, burst_size=200, window_seconds=0
            )

    def test_default_window_seconds(self) -> None:
        config = RateLimitConfig(requests_per_minute=100, burst_size=200)
        assert config.window_seconds == 60
