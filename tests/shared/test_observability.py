"""Observability primitives tests (Rules §6)."""

from __future__ import annotations

import pytest

from prism.shared.domain.observability import AICallLog, hash_prompt
from prism.shared.infrastructure.observability import (
    InMemoryMetrics,
    LoggingAICallRecorder,
    current_correlation_id,
    set_correlation_id,
    timed,
)


def test_hash_prompt_is_stable_and_pseudonymous() -> None:
    a = hash_prompt("hello world")
    b = hash_prompt("hello world")
    c = hash_prompt("hello world!")
    assert a == b
    assert a != c
    assert len(a) == 64  # sha256 hex


def test_correlation_id_contextvar_round_trip() -> None:
    set_correlation_id("cid-fixed")
    assert current_correlation_id() == "cid-fixed"


def test_in_memory_metrics_red() -> None:
    m = InMemoryMetrics()
    m.incr("http_requests_total", {"route": "/x", "status": "200"})
    m.incr("http_requests_total", {"route": "/x", "status": "200"})
    m.observe("http_request_duration_ms", 12.5, {"route": "/x"})
    keys = list(m.counters.keys())
    assert any("/x" in k for k in keys)
    assert sum(m.counters.values()) == 2
    assert any(v == [12.5] for v in m.histograms.values())


def test_timed_yields_elapsed_ms() -> None:
    with timed() as t:
        sum(range(1000))
    assert t["ms"] >= 0.0


@pytest.mark.asyncio
async def test_ai_call_recorder_emits_structured_log(caplog) -> None:  # type: ignore[no-untyped-def]
    import logging

    rec = LoggingAICallRecorder()
    log = AICallLog(
        model_id="gemini-2.5-pro",
        model_version="2026-05",
        prompt_hash=hash_prompt("describe this product"),
        tokens_in=120,
        tokens_out=300,
        latency_ms=842.0,
        cost_usd=0.0021,
        correlation_id="cid-1",
        tenant_id="gucci",
    )
    with caplog.at_level(logging.INFO, logger="prism.aicall"):
        await rec.record(log)
    assert any("ai_call" in r.message for r in caplog.records)
