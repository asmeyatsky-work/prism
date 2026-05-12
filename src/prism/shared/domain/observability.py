"""
Shared Domain — Observability Ports

Architectural Intent (Rules §6):
- OpenTelemetry tracing, propagated through MCP calls.
- RED metrics (Rate, Errors, Duration) per endpoint and per MCP tool.
- Structured JSON logs with correlation IDs. Zero PII.
- Per AI call log: model ID, version, prompt hash, tokens in/out, latency, cost.

This module defines the *ports*. Implementations live in
prism.shared.infrastructure.observability — domain stays SDK-free.

Layer: domain
Ports: TracerPort, MetricsPort, AICallRecorderPort
Stack: canonical.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


def hash_prompt(prompt: str) -> str:
    """SHA-256 of the prompt — never store the prompt itself (PII risk)."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AICallLog:
    """Immutable record of a single AI model invocation (Rules §6)."""

    model_id: str
    model_version: str
    prompt_hash: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    correlation_id: str = ""
    tenant_id: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)


class AICallRecorderPort(Protocol):
    """Sink for AI-call telemetry."""

    async def record(self, log: AICallLog) -> None: ...


class TracerPort(Protocol):
    """Minimal tracing port — wraps OTel without leaking the SDK into domain."""

    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> Any: ...


class MetricsPort(Protocol):
    """RED metrics port. Implementations buffer and export to OTel/Prometheus."""

    def incr(self, name: str, tags: dict[str, str] | None = None) -> None: ...

    def observe(self, name: str, value_ms: float, tags: dict[str, str] | None = None) -> None: ...
