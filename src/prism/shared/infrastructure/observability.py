"""
Shared Infrastructure — Observability Adapters

Architectural Intent:
- Correlation IDs propagated via contextvars + FastAPI middleware.
- structlog configured for JSON output with correlation_id binding.
- OTel-compatible tracer/metrics adapters — fall back to no-op when the
  opentelemetry SDK is not installed, so the domain remains import-safe.
- AICallRecorder writes to a dedicated 'prism.aicall' logger; production
  routes it to BigQuery for cost/latency dashboards.

Layer: infrastructure
Implements: TracerPort, MetricsPort, AICallRecorderPort
Stack: canonical (structlog, optional opentelemetry-api).
"""

from __future__ import annotations

import contextvars
import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator
from uuid import uuid4

from prism.shared.domain.observability import AICallLog

_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "prism_correlation_id", default=""
)


def current_correlation_id() -> str:
    cid = _correlation_id.get()
    if not cid:
        cid = str(uuid4())
        _correlation_id.set(cid)
    return cid


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)


def configure_logging() -> None:
    """Idempotent JSON-style log configuration. Zero PII by convention."""
    root = logging.getLogger()
    if getattr(configure_logging, "_done", False):  # type: ignore[attr-defined]
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
            '"msg":%(message)r,"correlation_id":"%(correlation_id)s"}'
        )
    )

    class _CIDFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            record.correlation_id = _correlation_id.get() or "-"
            return True

    handler.addFilter(_CIDFilter())
    root.handlers = [handler]
    root.setLevel(logging.INFO)
    configure_logging._done = True  # type: ignore[attr-defined]


class NoopTracer:
    """Tracer that no-ops when OTel is not configured."""

    @contextmanager
    def start_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Iterator[dict[str, Any]]:
        span: dict[str, Any] = {"name": name, "attributes": attributes or {}}
        yield span


class InMemoryMetrics:
    """RED metrics buffer suitable for tests and demo. Export adapter optional."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.histograms: dict[str, list[float]] = {}

    def incr(self, name: str, tags: dict[str, str] | None = None) -> None:
        key = self._key(name, tags)
        self.counters[key] = self.counters.get(key, 0) + 1

    def observe(
        self, name: str, value_ms: float, tags: dict[str, str] | None = None
    ) -> None:
        key = self._key(name, tags)
        self.histograms.setdefault(key, []).append(value_ms)

    @staticmethod
    def _key(name: str, tags: dict[str, str] | None) -> str:
        if not tags:
            return name
        return name + "{" + ",".join(f"{k}={v}" for k, v in sorted(tags.items())) + "}"


class LoggingAICallRecorder:
    """Writes one JSON line per AI call to the 'prism.aicall' logger."""

    def __init__(self, logger_name: str = "prism.aicall") -> None:
        self._log = logging.getLogger(logger_name)

    async def record(self, log: AICallLog) -> None:
        self._log.info(
            "ai_call",
            extra={
                "ai_call": {
                    "model_id": log.model_id,
                    "model_version": log.model_version,
                    "prompt_hash": log.prompt_hash,
                    "tokens_in": log.tokens_in,
                    "tokens_out": log.tokens_out,
                    "latency_ms": log.latency_ms,
                    "cost_usd": log.cost_usd,
                    "correlation_id": log.correlation_id,
                    "tenant_id": log.tenant_id,
                    "occurred_at": log.occurred_at.isoformat(),
                }
            },
        )


@contextmanager
def timed() -> Iterator[dict[str, float]]:
    """Stopwatch helper — yields a dict whose 'ms' is populated on exit."""
    out: dict[str, float] = {"ms": 0.0}
    start = time.perf_counter()
    try:
        yield out
    finally:
        out["ms"] = (time.perf_counter() - start) * 1000.0
