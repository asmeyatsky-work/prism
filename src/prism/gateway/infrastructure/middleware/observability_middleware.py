"""
Gateway Infrastructure — Observability Middleware

Architectural Intent (Rules §4, §6):
- Reads incoming X-Correlation-Id, generates one if missing, propagates via
  contextvar so every log line + audit event + AI-call record correlates.
- Emits RED metrics (Rate, Errors, Duration) per route.
- Returns the correlation id on the response so downstream services and
  client tooling can chain traces.

Layer: infrastructure (gateway bounded context)
Implements: FastAPI middleware glue around the domain TracerPort/MetricsPort.
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable
from uuid import uuid4

from prism.shared.infrastructure.observability import (
    InMemoryMetrics,
    set_correlation_id,
)


class ObservabilityMiddleware:
    """ASGI middleware emitting correlation ids + RED metrics per request."""

    HEADER = "x-correlation-id"

    def __init__(self, metrics: InMemoryMetrics | None = None) -> None:
        self.metrics = metrics or InMemoryMetrics()

    async def __call__(
        self,
        request: Any,
        call_next: Callable[[Any], Awaitable[Any]],
    ) -> Any:
        cid = request.headers.get(self.HEADER) or str(uuid4())
        set_correlation_id(cid)

        route = request.url.path
        method = request.method
        start = time.perf_counter()
        status = "200"
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        except Exception:
            status = "500"
            self.metrics.incr("http_errors_total", {"route": route, "method": method})
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            tags = {"route": route, "method": method, "status": status}
            self.metrics.incr("http_requests_total", tags)
            self.metrics.observe("http_request_duration_ms", elapsed_ms, tags)
            try:
                response.headers[self.HEADER] = cid  # type: ignore[possibly-unbound]
            except Exception:
                pass
