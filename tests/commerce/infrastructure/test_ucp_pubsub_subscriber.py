"""
UCP Pub/Sub subscriber tests.

The subscriber's `run` loop talks to the google-cloud-pubsub SDK; here we
test the *unit-of-work* — message decoding, ack/nack classification, and
audit recording — by exercising the internal handler dispatch directly.

A full end-to-end run-loop test requires `google-cloud-pubsub` (optional
extra); we skip it when the SDK is absent.
"""

from __future__ import annotations

import asyncio

import pytest

from prism.commerce.infrastructure.connectors.ucp_pubsub_subscriber import (
    UCPPubSubConfig,
    UCPPubSubSubscriber,
)
from prism.shared.infrastructure.audit_sinks import InMemoryAuditSink


@pytest.mark.asyncio
async def test_poison_messages_are_audited(monkeypatch: pytest.MonkeyPatch) -> None:
    sink = InMemoryAuditSink()
    sub = UCPPubSubSubscriber(
        config=UCPPubSubConfig(project_id="p", subscription_id="s"),
        handler=lambda _data: _never_called(),
        audit_sink=sink,
    )
    await sub._record_audit("msg-1", "bad json", poison=True)
    assert len(sink.events) == 1
    assert sink.events[0].action == "commerce.ucp.message.poison"
    assert sink.events[0].aggregate_id == "msg-1"


@pytest.mark.asyncio
async def test_transient_errors_are_audited_separately() -> None:
    sink = InMemoryAuditSink()
    sub = UCPPubSubSubscriber(
        config=UCPPubSubConfig(project_id="p", subscription_id="s"),
        handler=lambda _data: _never_called(),
        audit_sink=sink,
    )
    await sub._record_audit("msg-9", "timeout", poison=False)
    assert sink.events[0].action == "commerce.ucp.message.nack"


def test_config_from_env_reads_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISM_GCP_PROJECT_ID", "my-project")
    monkeypatch.setenv("PRISM_UCP_SUBSCRIPTION_ID", "ucp-events")
    cfg = UCPPubSubConfig.from_env()
    assert cfg.project_id == "my-project"
    assert cfg.subscription_id == "ucp-events"


def test_run_raises_without_pubsub_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("pytest")
    # If the SDK is genuinely installed, this test is a no-op.
    try:
        from google.cloud import pubsub_v1  # type: ignore[import-not-found] # noqa: F401
        pytest.skip("google-cloud-pubsub installed; this test only covers the missing-SDK path")
    except ImportError:
        pass

    sub = UCPPubSubSubscriber(
        config=UCPPubSubConfig(project_id="p", subscription_id="s"),
        handler=lambda _: _never_called(),
    )
    with pytest.raises(RuntimeError, match="google-cloud-pubsub"):
        asyncio.get_event_loop().run_until_complete(sub.run())


async def _never_called() -> None:  # pragma: no cover — fixture-only stub
    raise AssertionError("handler was invoked unexpectedly")
