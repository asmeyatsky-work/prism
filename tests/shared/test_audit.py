"""Audit event port + sink tests (Rules §4)."""

from __future__ import annotations

import pytest

from prism.shared.domain.audit import AuditEvent, _hash
from prism.shared.infrastructure.audit_sinks import InMemoryAuditSink


def test_for_change_hashes_before_and_after_deterministically() -> None:
    before = {"status": "RAW", "qs": 0.0}
    after = {"qs": 0.0, "status": "RAW"}  # different key order
    ev = AuditEvent.for_change(
        actor="api:gucci",
        action="catalogue.ingest_product",
        aggregate_type="Product",
        aggregate_id="abc",
        tenant_id="gucci",
        before=before,
        after=after,
    )
    # canonical JSON => same hash despite key order.
    assert ev.before_hash == ev.after_hash == _hash(before)


def test_for_change_with_none_payload_yields_empty_hash() -> None:
    ev = AuditEvent.for_change(
        actor="api:x",
        action="x",
        aggregate_type="X",
        aggregate_id="1",
        tenant_id="t",
        before=None,
        after={"v": 1},
    )
    assert ev.before_hash == ""
    assert ev.after_hash != ""


def test_audit_event_to_dict_round_trip_is_jsonable() -> None:
    import json

    ev = AuditEvent.for_change(
        actor="api:t",
        action="a",
        aggregate_type="T",
        aggregate_id="1",
        tenant_id="t",
        before={"a": 1},
        after={"a": 2},
        correlation_id="cid-1",
    )
    payload = json.dumps(ev.to_dict())
    parsed = json.loads(payload)
    assert parsed["correlation_id"] == "cid-1"
    assert parsed["actor"] == "api:t"


@pytest.mark.asyncio
async def test_in_memory_sink_is_append_only() -> None:
    sink = InMemoryAuditSink()
    ev = AuditEvent.for_change(
        actor="x",
        action="y",
        aggregate_type="Z",
        aggregate_id="1",
        tenant_id="t",
        before=None,
        after={"v": 1},
    )
    await sink.record(ev)
    await sink.record(ev)
    assert len(sink.events) == 2
    # `events` returns an immutable copy — mutating it doesn't affect the sink.
    snapshot = sink.events
    assert isinstance(snapshot, tuple)
