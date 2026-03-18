"""
Gateway Presentation — Main API Router

Architectural Intent:
- Aggregates all bounded-context API routes into a single Starlette/FastAPI application
- Mounts health, catalogue, intelligence, discovery, tryon, commerce, payment, and agentic_cx
- Applies authentication and tenant middleware globally
- Serves as the single entry point for all PRISM API traffic
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from prism.gateway.domain.ports.gateway_ports import (
    APIKeyRepositoryPort,
    RateLimiterPort,
    TenantConfigPort,
)
from prism.gateway.infrastructure.middleware.auth_middleware import (
    APIKeyAuthMiddleware,
)
from prism.gateway.infrastructure.middleware.tenant_middleware import (
    TenantContextMiddleware,
)
from prism.gateway.presentation.api.health import health_routes

logger = logging.getLogger(__name__)


async def _root(request: Request) -> JSONResponse:
    """Root endpoint returning API metadata."""
    return JSONResponse(
        {
            "service": "PRISM Unified Commerce Intelligence Platform",
            "version": "1.0.0",
            "documentation": "/docs",
            "health": "/health",
            "bounded_contexts": [
                "catalogue",
                "intelligence",
                "discovery",
                "tryon",
                "commerce",
                "payment",
                "reconciliation",
                "agentic_cx",
            ],
        }
    )


async def _not_found(request: Request, exc: Exception) -> JSONResponse:
    """Custom 404 handler."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "not_found",
            "message": f"The path {request.url.path} does not exist.",
        },
    )


async def _server_error(request: Request, exc: Exception) -> JSONResponse:
    """Custom 500 handler."""
    logger.exception("Unhandled server error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


def create_gateway_app(
    key_repository: APIKeyRepositoryPort,
    rate_limiter: RateLimiterPort,
    tenant_config_port: TenantConfigPort,
    context_routes: dict[str, list[Route]] | None = None,
) -> Starlette:
    """
    Create the main PRISM Gateway Starlette application.

    Args:
        key_repository: Port for API key validation.
        rate_limiter: Port for request rate limiting.
        tenant_config_port: Port for tenant configuration lookup.
        context_routes: Optional mapping of bounded-context name -> routes
                        to mount under ``/api/v1/{context_name}``.

    Returns:
        Configured Starlette application with middleware and routes.
    """
    routes: list[Route | Mount] = [
        Route("/", endpoint=_root, methods=["GET"]),
        *health_routes,
    ]

    # Mount bounded-context routes under /api/v1/{context}
    if context_routes:
        for context_name, ctx_routes in context_routes.items():
            routes.append(
                Mount(
                    f"/api/v1/{context_name}",
                    routes=ctx_routes,
                    name=context_name,
                )
            )

    middleware = [
        Middleware(
            APIKeyAuthMiddleware,
            key_repository=key_repository,
            rate_limiter=rate_limiter,
        ),
        Middleware(
            TenantContextMiddleware,
            tenant_config_port=tenant_config_port,
        ),
    ]

    exception_handlers: dict[int, Any] = {
        404: _not_found,
        500: _server_error,
    }

    app = Starlette(
        routes=routes,
        middleware=middleware,
        exception_handlers=exception_handlers,
        debug=False,
    )

    # Mark startup as complete for the startup probe
    app.state.startup_complete = True
    app.state.health_checkers = {}

    logger.info(
        "PRISM Gateway created with %d route mounts", len(context_routes or {})
    )

    return app
