# 0005 — Observability: contextvar correlation IDs

Status: Accepted
Date: 2026-05-12

## Context

Rules §6 requires:
- OpenTelemetry tracing, propagated through MCP calls.
- Structured JSON logs with correlation IDs.
- Per-AI-call log: model id, version, prompt hash, tokens, latency, cost.

## Decision

Correlation IDs propagate via `contextvars.ContextVar`. Reasons:

- `contextvars` is asyncio-safe and survives `await` boundaries — no
  thread-local pitfalls under FastAPI.
- The `ObservabilityMiddleware` reads `X-Correlation-Id` from the inbound
  request (or generates a UUID), sets the contextvar, and writes the id
  back on the response.
- The same id is read by `AuditEvent.for_change(correlation_id=...)` and
  by `LoggingAICallRecorder` — every audit row and every AI-call log
  joins on a single id.
- `OpenTelemetry` integration is via the contextvar bridge in the OTel
  Python contrib. Today we ship a `NoopTracer`; switching to the OTel
  exporter is a config change, not a code change.

## Consequences

- All MCP server adapters must call
  `prism.shared.infrastructure.observability.set_correlation_id` when
  receiving a request from outside the process (e.g. SSE transport).
- New AI adapters must populate `AICallLog.correlation_id =
  current_correlation_id()` before calling the recorder.
