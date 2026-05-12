# 0006 — UCP integration: three-layer adapter strategy

Status: Accepted
Date: 2026-05-12

## Context

UCP (Unified Commerce Protocol) is the upstream system PRISM enriches. The
PRD requires bidirectional sync — PRISM consumes UCP events, enriches the
catalogue, and pushes the enriched payload back to UCP and to Google
Shopping.

Three different deployment shapes need to coexist:

- **Demo / local**: no external UCP service is available; tests and
  marketing demos must work offline.
- **Staging**: a real UCP HTTP endpoint is reachable but Pub/Sub is not
  yet provisioned.
- **Production**: UCP delivers events via Pub/Sub; PRISM also pushes
  outbound updates over HTTPS.

## Decision

Ship the UCP integration as **three layered components**, selected at
runtime via configuration. Each is a separate adapter behind the same
domain ports (`UCPInboundPort`, `UCPOutboundPort`).

| Layer                | Module                                                                   | When active                                |
|----------------------|---------------------------------------------------------------------------|--------------------------------------------|
| Mock                 | `prism.demo.mocks.commerce_mocks.MockUCPInbound/Outbound`                | default — when feature flag is off         |
| HTTP                 | `prism.commerce.infrastructure.adapters.ucp_http_adapter.UCPHttpAdapter` | `PRISM_UCP_HTTP_ENABLED=1`                 |
| Pub/Sub subscriber   | `prism.commerce.infrastructure.connectors.ucp_pubsub_subscriber`        | started by `bootstrap.py` in production    |

The Pub/Sub subscriber is *additive*: it drives `ProcessUCPEventUseCase`
from upstream messages, but the same use case is reachable via the demo
endpoint `POST /api/commerce/ucp/events`. Both paths converge on identical
domain logic — there is exactly one `UCPInboundPort` implementation in
play at any time.

## Consequences

- New environment variables (loaded via Secret Manager in production):
  `PRISM_UCP_HTTP_ENABLED`, `PRISM_UCP_BASE_URL`, `PRISM_UCP_API_KEY`,
  `PRISM_GCP_PROJECT_ID`, `PRISM_UCP_SUBSCRIPTION_ID`.
- HTTP adapter has bounded retry (exponential backoff, max 2 retries) and
  a 10s timeout — no unbounded waits (Rules §4).
- Pub/Sub subscriber distinguishes poison messages (ack to break the
  loop) from transient failures (nack to redeliver); every poison and
  every nack emits an `AuditEvent` (Rules §4).
- All UCP inbound paths emit `commerce.ucp.event_received` audit events
  scoped by tenant. Outbound pushes are best-effort and emit success/fail
  in the API response.
