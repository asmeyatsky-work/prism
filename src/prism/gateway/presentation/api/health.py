"""
Gateway Presentation — Health Check and Readiness Endpoints

Architectural Intent:
- Kubernetes-compatible health probes: liveness, readiness, and startup
- Aggregates health from all registered bounded-context services
- Returns structured HealthCheckDTO for monitoring dashboards
- No authentication required — these are infrastructure endpoints
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from prism.gateway.application.dtos.gateway_dto import (
    HealthCheckDTO,
    ServiceHealthDTO,
    ServiceStatus,
)

logger = logging.getLogger(__name__)

# Application start time for uptime calculation
_START_TIME = time.monotonic()

# Version is injected at build time; default for development
_VERSION = "1.0.0"


async def liveness(request: Request) -> JSONResponse:
    """
    Kubernetes liveness probe.

    Returns 200 if the process is running. This endpoint does NOT check
    downstream dependencies — that is the readiness probe's job.
    """
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


async def readiness(request: Request) -> JSONResponse:
    """
    Kubernetes readiness probe.

    Checks connectivity to critical infrastructure (Redis, database)
    and all registered bounded-context services. Returns 503 if any
    critical dependency is unhealthy.
    """
    services: list[ServiceHealthDTO] = []
    overall_status = ServiceStatus.HEALTHY

    # Check registered service health checkers from app state
    health_checkers: dict[str, Any] = getattr(
        request.app.state, "health_checkers", {}
    )

    for name, checker in health_checkers.items():
        start = time.monotonic()
        try:
            is_healthy = await checker()
            latency = (time.monotonic() - start) * 1000
            status = ServiceStatus.HEALTHY if is_healthy else ServiceStatus.UNHEALTHY
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            status = ServiceStatus.UNHEALTHY
            logger.warning("Health check failed for %s: %s", name, str(exc))

        if status != ServiceStatus.HEALTHY:
            overall_status = ServiceStatus.DEGRADED

        services.append(
            ServiceHealthDTO(
                name=name,
                status=status,
                latency_ms=round(latency, 2),
            )
        )

    health = HealthCheckDTO(
        status=overall_status,
        version=_VERSION,
        timestamp=datetime.now(UTC),
        services=services,
        uptime_seconds=round(time.monotonic() - _START_TIME, 2),
    )

    status_code = 200 if overall_status == ServiceStatus.HEALTHY else 503

    return JSONResponse(
        status_code=status_code,
        content=health.model_dump(mode="json"),
    )


async def startup(request: Request) -> JSONResponse:
    """
    Kubernetes startup probe.

    Returns 200 once the application has completed initialisation.
    Used for slow-starting containers to avoid premature liveness failures.
    """
    is_ready = getattr(request.app.state, "startup_complete", False)

    if is_ready:
        return JSONResponse(
            status_code=200,
            content={"status": "started"},
        )

    return JSONResponse(
        status_code=503,
        content={"status": "starting"},
    )


# Route definitions for inclusion in the main router
health_routes = [
    Route("/health", endpoint=liveness, methods=["GET"]),
    Route("/health/live", endpoint=liveness, methods=["GET"]),
    Route("/health/ready", endpoint=readiness, methods=["GET"]),
    Route("/health/startup", endpoint=startup, methods=["GET"]),
]
