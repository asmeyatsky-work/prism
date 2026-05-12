"""
Commerce Infrastructure — UCP Pub/Sub Subscriber

Architectural Intent:
- Pulls UCP events from a Google Pub/Sub subscription and dispatches each
  message to the application-layer ProcessUCPEventUseCase.
- The Pub/Sub client is lazily imported so the demo + unit tests don't
  require the google-cloud-pubsub package at install time (it lives under
  the [gcp] extra).
- Bounded inflight count + ack/nack semantics: a transient handler failure
  nacks the message so Pub/Sub redelivers; permanent failures (validation)
  ack to avoid poison loops, and emit an audit event for forensics.
- Designed to be started from prism.bootstrap and run as a long-lived
  task — gracefully cancellable.

Layer: infrastructure
Implements: external integration glue (no port — this is an inbound driver).
Stack: canonical (google-cloud-pubsub via [gcp] extra).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from prism.shared.domain.audit import AuditEvent, AuditSinkPort
from prism.shared.infrastructure.observability import set_correlation_id

logger = logging.getLogger("prism.commerce.ucp_pubsub")


@dataclass(frozen=True)
class UCPPubSubConfig:
    """Configuration loaded from env vars in production deployments."""

    project_id: str
    subscription_id: str
    max_messages: int = 10
    ack_deadline_seconds: int = 30

    @classmethod
    def from_env(cls) -> "UCPPubSubConfig":
        return cls(
            project_id=os.environ["PRISM_GCP_PROJECT_ID"],
            subscription_id=os.environ.get(
                "PRISM_UCP_SUBSCRIPTION_ID", "prism-ucp-events"
            ),
            max_messages=int(os.environ.get("PRISM_UCP_MAX_MESSAGES", "10")),
        )


# Handler signature: receives the decoded event-data dict + correlation id,
# returns nothing on success, raises on transient failure (so we nack).
EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class UCPPubSubSubscriber:
    """
    Long-lived consumer that drains a UCP Pub/Sub subscription.

    Production wiring (in bootstrap):

        sub = UCPPubSubSubscriber(
            config=UCPPubSubConfig.from_env(),
            handler=lambda data: workflow.execute(data),
            audit_sink=audit_sink,
        )
        asyncio.create_task(sub.run())
    """

    def __init__(
        self,
        *,
        config: UCPPubSubConfig,
        handler: EventHandler,
        audit_sink: AuditSinkPort | None = None,
    ) -> None:
        self._config = config
        self._handler = handler
        self._audit_sink = audit_sink
        self._stopping = asyncio.Event()

    def stop(self) -> None:
        self._stopping.set()

    async def run(self) -> None:
        """
        Pull-loop. Imports the Pub/Sub SDK lazily so the demo container
        doesn't require the [gcp] extra at install time.
        """
        try:
            from google.cloud import pubsub_v1  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "google-cloud-pubsub not installed — install the [gcp] extra "
                "to enable the UCP Pub/Sub subscriber"
            ) from exc

        subscriber = pubsub_v1.SubscriberClient()
        path = subscriber.subscription_path(
            self._config.project_id, self._config.subscription_id
        )
        logger.info("UCP Pub/Sub subscriber starting on %s", path)

        loop = asyncio.get_running_loop()

        while not self._stopping.is_set():
            try:
                resp = await loop.run_in_executor(
                    None,
                    lambda: subscriber.pull(
                        request={
                            "subscription": path,
                            "max_messages": self._config.max_messages,
                        },
                        timeout=10.0,
                    ),
                )
            except Exception:  # pragma: no cover — network/SDK errors
                logger.exception("UCP Pub/Sub pull failed; backing off 1s")
                await asyncio.sleep(1.0)
                continue

            to_ack: list[str] = []
            to_nack: list[str] = []

            for msg in resp.received_messages:
                ack_id = msg.ack_id
                try:
                    payload = json.loads(msg.message.data.decode("utf-8"))
                    correlation_id = msg.message.attributes.get(
                        "x-correlation-id", ""
                    )
                    if correlation_id:
                        set_correlation_id(correlation_id)
                    await self._handler(payload)
                    to_ack.append(ack_id)
                except ValueError as exc:
                    # Permanent: bad JSON / schema. Ack so it doesn't loop.
                    logger.warning("Poison UCP message %s: %s", msg.message.message_id, exc)
                    await self._record_audit(msg.message.message_id, str(exc), poison=True)
                    to_ack.append(ack_id)
                except Exception as exc:
                    # Transient: nack to retry.
                    logger.warning(
                        "Transient UCP handler error %s: %s",
                        msg.message.message_id,
                        exc,
                    )
                    await self._record_audit(msg.message.message_id, str(exc), poison=False)
                    to_nack.append(ack_id)

            if to_ack:
                await loop.run_in_executor(
                    None,
                    lambda: subscriber.acknowledge(
                        request={"subscription": path, "ack_ids": to_ack}
                    ),
                )
            if to_nack:
                await loop.run_in_executor(
                    None,
                    lambda: subscriber.modify_ack_deadline(
                        request={
                            "subscription": path,
                            "ack_ids": to_nack,
                            "ack_deadline_seconds": 0,
                        }
                    ),
                )

        logger.info("UCP Pub/Sub subscriber stopped")

    async def _record_audit(
        self, message_id: str, reason: str, *, poison: bool
    ) -> None:
        if self._audit_sink is None:
            return
        await self._audit_sink.record(
            AuditEvent.for_change(
                actor="ucp-pubsub-subscriber",
                action="commerce.ucp.message.poison"
                if poison
                else "commerce.ucp.message.nack",
                aggregate_type="UCPMessage",
                aggregate_id=message_id,
                tenant_id="",
                before=None,
                after={"reason": reason},
            )
        )
