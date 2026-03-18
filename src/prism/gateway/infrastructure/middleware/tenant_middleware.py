"""
Gateway Infrastructure — Tenant Context Middleware

Architectural Intent:
- Extracts tenant identity from the validated API key
- Constructs a TenantContext and injects it into request.state
- All downstream handlers and services receive tenant-scoped context
- Must run AFTER APIKeyAuthMiddleware in the middleware stack
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from prism.shared.application.dtos import TenantContext
from prism.gateway.domain.ports.gateway_ports import TenantConfigPort

logger = logging.getLogger(__name__)

# Paths that bypass tenant extraction (same as auth middleware)
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/health/ready",
        "/health/live",
        "/docs",
        "/openapi.json",
    }
)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that resolves tenant context from the authenticated API key.

    After ``APIKeyAuthMiddleware`` attaches ``request.state.api_key``, this
    middleware looks up the tenant configuration and builds a ``TenantContext``
    at ``request.state.tenant_context``.

    If the tenant configuration is missing or the tenant is disabled, the
    request is rejected with a 403.
    """

    def __init__(self, app: Any, tenant_config_port: TenantConfigPort) -> None:
        super().__init__(app)
        self._tenant_config_port = tenant_config_port

    async def dispatch(
        self, request: Request, call_next: Callable[..., Any]
    ) -> Response:
        # Skip public paths
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Require a validated API key from the auth middleware
        api_key = getattr(request.state, "api_key", None)
        if api_key is None:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "missing_context",
                    "message": "No authenticated API key found in request.",
                },
            )

        try:
            tenant_config = await self._tenant_config_port.get_config(
                api_key.tenant_id
            )
        except (KeyError, LookupError):
            logger.error(
                "Tenant config not found: tenant_id=%s", api_key.tenant_id.value
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "tenant_not_found",
                    "message": "Tenant configuration could not be resolved.",
                },
            )

        # Build and inject tenant context
        tenant_context = TenantContext(
            tenant_id=api_key.tenant_id.value,
            brand_name=tenant_config.brand_name,
        )

        request.state.tenant_context = tenant_context
        request.state.tenant_config = tenant_config

        logger.debug(
            "Tenant context resolved: tenant_id=%s brand=%s",
            tenant_context.tenant_id,
            tenant_context.brand_name,
        )

        return await call_next(request)
