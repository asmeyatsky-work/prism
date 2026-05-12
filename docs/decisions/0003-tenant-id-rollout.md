# 0003 — Tenant-id rollout across MCP tool surfaces

Status: Accepted
Date: 2026-05-12

## Context

Rules §3 #5 requires "One MCP server per bounded context" and the platform
is multi-tenant (one brand per tenant). Several MCP tools were authored
before the multi-tenant policy was finalised and do not declare
`tenant_id` on their input schema; instead they rely on the calling
session for tenant scoping.

## Decision

1. **Server-level invariant** (enforced today, via
   `tests/mcp/test_mcp_schema_round_trip.py`): every MCP server must
   declare `tenant_id` on at least one tool. CI fails if any bounded
   context's server is wholly tenant-blind.

2. **Tool-level rollout** (next milestone): we will progressively add a
   `tenant_id` parameter to *every* MCP tool's input schema. Until then,
   tools missing it rely on `app.state.tenant_context` set by the
   `tenant_middleware` in the gateway.

## Consequences

- New MCP tools MUST include `tenant_id` from inception.
- A follow-up PR will add `tenant_id` to:
  - `commerce.process_ucp_event`, `commerce.push_enriched_product`
  - `intelligence.generate_description`, `intelligence.extract_attributes`
  - `payment.capture_payment`, `payment.refund_payment`
  - `agentic_cx.handle_message` (currently `customer_id`-scoped only)
