"""
Gateway Infrastructure — API Key Authentication Middleware

Architectural Intent:
- Validates API keys from the X-API-Key request header
- Checks key validity, scope authorisation, and rate limits
- Returns appropriate HTTP error codes: 401, 403, 429
- Stateless middleware — all state is in the key repository and rate limiter
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from prism.gateway.domain.ports.gateway_ports import APIKeyRepositoryPort, RateLimiterPort
from prism.gateway.domain.value_objects.api_types import RateLimitConfig

logger = logging.getLogger(__name__)

# Header name for API key authentication
API_KEY_HEADER = "X-API-Key"

# Paths that do not require authentication
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/health/ready",
        "/health/live",
        "/docs",
        "/openapi.json",
    }
)


def _hash_key(raw_key: str) -> str:
    """Produce a SHA-256 hex digest of the raw API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that authenticates requests via API key.

    Flow:
    1. Skip authentication for public paths (health, docs).
    2. Extract key from ``X-API-Key`` header; 401 if missing.
    3. Hash the key and look it up in the repository; 401 if unknown.
    4. Verify key validity (enabled, not expired); 401 if invalid.
    5. Check rate limit; 429 if exceeded.
    6. Attach the validated API key to ``request.state.api_key``.
    """

    def __init__(
        self,
        app: Any,
        key_repository: APIKeyRepositoryPort,
        rate_limiter: RateLimiterPort,
    ) -> None:
        super().__init__(app)
        self._key_repository = key_repository
        self._rate_limiter = rate_limiter

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        # Allow public endpoints through without authentication
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Extract API key from header
        raw_key = request.headers.get(API_KEY_HEADER)
        if not raw_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "missing_api_key",
                    "message": f"The {API_KEY_HEADER} header is required.",
                },
            )

        # Hash and validate
        key_hash = _hash_key(raw_key)
        api_key = await self._key_repository.validate_key(key_hash)
        if api_key is None:
            logger.warning("API key not found: hash=%s...", key_hash[:12])
            return JSONResponse(
                status_code=401,
                content={
                    "error": "invalid_api_key",
                    "message": "The provided API key is not recognised.",
                },
            )

        if not api_key.is_valid():
            reason = "disabled" if not api_key.enabled else "expired"
            logger.warning(
                "API key rejected: key_id=%s reason=%s", api_key.key_id, reason
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": f"api_key_{reason}",
                    "message": f"The API key is {reason}.",
                },
            )

        # Check rate limit
        limit_config = RateLimitConfig(
            requests_per_minute=api_key.rate_limit_per_minute,
            burst_size=api_key.rate_limit_per_minute * 2,
        )
        allowed = await self._rate_limiter.check_rate_limit(
            api_key.key_id, limit_config
        )
        if not allowed:
            logger.info("Rate limit exceeded: key_id=%s", api_key.key_id)
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Rate limit exceeded. Please retry later.",
                },
                headers={
                    "Retry-After": str(limit_config.window_seconds),
                    "X-RateLimit-Limit": str(api_key.rate_limit_per_minute),
                },
            )

        # Record the request and attach key to request state
        await self._rate_limiter.record_request(api_key.key_id)
        request.state.api_key = api_key

        return await call_next(request)


def require_scope(scope: str) -> Callable[..., Any]:
    """
    Dependency function for FastAPI/Starlette route-level scope checks.

    Usage::

        @router.get("/admin/keys", dependencies=[Depends(require_scope("admin:full"))])
        async def list_keys(request: Request): ...
    """

    async def _check_scope(request: Request) -> None:
        api_key = getattr(request.state, "api_key", None)
        if api_key is None:
            raise _forbidden("No API key in request context.")
        if not api_key.has_scope(scope):
            raise _forbidden(
                f"API key '{api_key.name}' lacks required scope: {scope}"
            )

    return _check_scope


def _forbidden(detail: str) -> Exception:
    """Create a 403 HTTP exception."""
    from starlette.exceptions import HTTPException

    return HTTPException(status_code=403, detail=detail)
