"""Demo-API UCP endpoint tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from prism.demo.api.app import create_app


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_ucp_status_defaults_to_mock(client: TestClient) -> None:
    resp = client.get("/api/commerce/ucp/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["http_enabled"] is False
    assert body["transport"] == "mock"
    assert body["pubsub_supported"] is True


def test_receive_ucp_event_accepts_envelope(client: TestClient) -> None:
    payload = {
        "event_id": "evt-100",
        "event_type": "product.updated",
        "source": "gucci",
        "payload": {"sku": "G-001", "price": 1200},
    }
    resp = client.post("/api/commerce/ucp/events", json=payload, headers={"X-Tenant-ID": "gucci"})
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["event_type"] == "PRODUCT_UPDATED"
    assert body["status"] in {"PROCESSED", "PROCESSING", "RECEIVED"}


def test_receive_ucp_event_rejects_missing_type(client: TestClient) -> None:
    resp = client.post(
        "/api/commerce/ucp/events",
        json={"event_id": "evt-99", "payload": {}},
        headers={"X-Tenant-ID": "gucci"},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert "VALIDATION" in (body["code"] or "")


def test_ingest_fans_out_to_ucp_outbound(client: TestClient) -> None:
    payload = {
        "tenant_id": "gucci",
        "sku": "G-FANOUT-1",
        "name": "Fan-out test bag",
        "brand": "Gucci",
        "price_amount": 2400,
        "price_currency": "EUR",
    }
    resp = client.post(
        "/api/catalogue/ingest", json=payload, headers={"X-Tenant-ID": "gucci"}
    )
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["success"] is True
    assert result["ucp_pushed"] is True


def test_audit_event_emitted_for_ucp_inbound(client: TestClient) -> None:
    # Tap into app.state.audit and read events.
    app = client.app
    audit = app.state.audit
    before = len(audit.events)
    client.post(
        "/api/commerce/ucp/events",
        json={
            "event_id": "evt-audit-1",
            "event_type": "product.created",
            "source": "burberry",
            "payload": {"sku": "BB-1"},
        },
        headers={"X-Tenant-ID": "burberry"},
    )
    new_events = [e for e in audit.events[before:] if e.action == "commerce.ucp.event_received"]
    assert new_events, "expected commerce.ucp.event_received audit event"
    assert new_events[0].tenant_id == "burberry"
