"""
Agentic CX — Memorystore (Redis) Cache

Architectural Intent:
- Short-term cache for frequently accessed data in the agent flow
- Implements a cache layer over SessionMemoryPort for hot data
- Uses Google Cloud Memorystore (Redis-compatible) in production
- Caches: active conversation state, customer profile snapshots, tool results
- TTL-based expiration ensures stale data is automatically purged
- Falls back to in-memory dict for local development
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MemorystoreCache:
    """
    Redis-compatible cache for short-term agent data.

    Provides low-latency access to frequently read data during
    agent interactions. Sits in front of Firestore for hot data
    like active conversation state and recent tool results.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        default_ttl_seconds: int = 3600,
        key_prefix: str = "prism:agentic_cx:",
    ) -> None:
        self._host = host
        self._port = port
        self._default_ttl_seconds = default_ttl_seconds
        self._key_prefix = key_prefix
        self._client: Any = None
        self._fallback: dict[str, tuple[Any, float]] = {}
        self._use_fallback = False

    async def _get_client(self) -> Any:
        """Lazily initialise the Redis client."""
        if self._use_fallback:
            return None
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.Redis(
                    host=self._host,
                    port=self._port,
                    decode_responses=True,
                )
                # Test connection
                await self._client.ping()
            except (ImportError, Exception) as e:
                logger.warning(
                    "Memorystore not available, using in-memory fallback: %s", str(e)
                )
                self._use_fallback = True
                return None
        return self._client

    def _make_key(self, key: str) -> str:
        """Build a namespaced cache key."""
        return f"{self._key_prefix}{key}"

    async def get(self, key: str) -> Any:
        """
        Retrieve a value from cache.

        Returns None on cache miss.
        """
        client = await self._get_client()
        if client is None:
            entry = self._fallback.get(self._make_key(key))
            return entry[0] if entry else None

        raw = await client.get(self._make_key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int | None = None,
    ) -> None:
        """
        Store a value in cache with optional TTL.

        Args:
            key: Cache key.
            value: Value to cache (must be JSON-serialisable).
            ttl_seconds: Time-to-live in seconds. Uses default if not provided.
        """
        ttl = ttl_seconds or self._default_ttl_seconds
        client = await self._get_client()
        if client is None:
            self._fallback[self._make_key(key)] = (value, ttl)
            return

        serialised = json.dumps(value, default=str)
        await client.set(self._make_key(key), serialised, ex=ttl)

    async def delete(self, key: str) -> None:
        """Remove a value from cache."""
        client = await self._get_client()
        if client is None:
            self._fallback.pop(self._make_key(key), None)
            return

        await client.delete(self._make_key(key))

    async def get_or_set(
        self,
        key: str,
        factory: Any,
        ttl_seconds: int | None = None,
    ) -> Any:
        """
        Retrieve from cache, or compute and cache if missing.

        Args:
            key: Cache key.
            factory: Async callable that produces the value on cache miss.
            ttl_seconds: TTL for the cached value.

        Returns:
            The cached or freshly computed value.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await factory()
        await self.set(key, value, ttl_seconds)
        return value

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a glob pattern.

        Useful for clearing all cached data for a conversation or customer.

        Returns the number of keys deleted.
        """
        full_pattern = self._make_key(pattern)
        client = await self._get_client()
        if client is None:
            keys_to_delete = [
                k for k in self._fallback if self._matches_glob(k, full_pattern)
            ]
            for k in keys_to_delete:
                del self._fallback[k]
            return len(keys_to_delete)

        keys = []
        async for key in client.scan_iter(match=full_pattern):
            keys.append(key)
        if keys:
            return await client.delete(*keys)
        return 0

    @staticmethod
    def _matches_glob(text: str, pattern: str) -> bool:
        """Simple glob matching for in-memory fallback."""
        import fnmatch

        return fnmatch.fnmatch(text, pattern)
