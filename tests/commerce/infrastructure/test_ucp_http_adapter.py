"""UCP HTTP adapter tests using httpx.MockTransport (no network)."""

from __future__ import annotations

import os

import httpx
import pytest

from prism.commerce.domain.entities.commerce_event import (
    CommerceEventType,
    ProcessingStatus,
)
from prism.commerce.domain.value_objects.ucp_schema import UCPEventEnvelope
from prism.commerce.infrastructure.adapters.ucp_http_adapter import (
    UCPHttpAdapter,
    ucp_http_enabled,
)


def _envelope(event_id: str = "evt-1", event_type: str = "product.updated") -> UCPEventEnvelope:
    return UCPEventEnvelope(
        event_id=event_id,
        event_type=event_type,
        source="gucci",
        payload=(("sku", "SKU-1"), ("price", 1200)),
    )


@pytest.mark.asyncio
async def test_receive_event_acks_and_dedups() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json={"ok": True})

    adapter = UCPHttpAdapter(
        base_url="https://ucp.example.com",
        api_key="t",
        transport=httpx.MockTransport(handler),
    )
    env = _envelope("evt-42")
    first = await adapter.receive_event(env)
    second = await adapter.receive_event(env)
    assert first.event_type is CommerceEventType.PRODUCT_UPDATED
    assert first.processing_status is ProcessingStatus.RECEIVED
    # Second call is idempotent — no second ack call.
    assert seen == ["/events/evt-42/ack"]
    assert second.processing_status is ProcessingStatus.RECEIVED
    await adapter.close()


@pytest.mark.asyncio
async def test_push_enriched_product_returns_true_on_2xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/products/enriched"
        return httpx.Response(201, json={"id": "ok"})

    adapter = UCPHttpAdapter(
        base_url="https://ucp.example.com",
        api_key="t",
        transport=httpx.MockTransport(handler),
    )
    ok = await adapter.push_enriched_product({"sku": "X"})
    assert ok is True
    await adapter.close()


@pytest.mark.asyncio
async def test_push_retries_on_5xx_then_succeeds() -> None:
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] < 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    adapter = UCPHttpAdapter(
        base_url="https://ucp.example.com",
        api_key="t",
        transport=httpx.MockTransport(handler),
        max_retries=2,
    )
    ok = await adapter.push_enriched_product({"sku": "X"})
    assert ok is True
    assert state["n"] == 2
    await adapter.close()


@pytest.mark.asyncio
async def test_push_returns_false_after_exhausting_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    adapter = UCPHttpAdapter(
        base_url="https://ucp.example.com",
        api_key="t",
        transport=httpx.MockTransport(handler),
        max_retries=1,
    )
    ok = await adapter.push_enriched_product({"sku": "X"})
    assert ok is False
    await adapter.close()


def test_feature_flag_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISM_UCP_HTTP_ENABLED", raising=False)
    assert ucp_http_enabled() is False
    monkeypatch.setenv("PRISM_UCP_HTTP_ENABLED", "1")
    assert ucp_http_enabled() is True


def test_from_env_requires_url_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISM_UCP_BASE_URL", raising=False)
    monkeypatch.delenv("PRISM_UCP_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        UCPHttpAdapter.from_env()
