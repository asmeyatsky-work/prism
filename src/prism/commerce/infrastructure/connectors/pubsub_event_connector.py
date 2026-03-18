"""
Commerce Infrastructure Connector — Pub/Sub Event Connector

Architectural Intent:
- Subscribes to Google Cloud Pub/Sub topics for UCP event streams
- Deserialises Pub/Sub messages into UCPEventEnvelope value objects
- Forwards deserialized events to the ProcessUCPEventUseCase
- Handles acknowledgement, nack on failure, and dead-letter routing
- Parallelism-first: processes messages concurrently with bounded concurrency
- Per skill2026 Rule 7: backpressure via flow control settings

Message Flow:
  Pub/Sub subscription -> deserialise -> ProcessUCPEventUseCase -> ack/nack
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class PubSubEventConnector:
    """
    Pub/Sub subscription connector for inbound UCP commerce events.

    Listens on a Pub/Sub subscription and forwards each message to a
    processing callback (typically ProcessUCPEventUseCase.execute).
    Manages concurrency, acknowledgement, and error handling.
    """

    def __init__(
        self,
        project_id: str,
        subscription_id: str,
        max_concurrent_messages: int = 10,
        ack_deadline_seconds: int = 60,
    ) -> None:
        """
        Initialise the Pub/Sub event connector.

        Args:
            project_id: GCP project ID.
            subscription_id: Pub/Sub subscription ID to pull from.
            max_concurrent_messages: Maximum messages processed concurrently.
            ack_deadline_seconds: Deadline for message acknowledgement.
        """
        self._project_id = project_id
        self._subscription_id = subscription_id
        self._max_concurrent = max_concurrent_messages
        self._ack_deadline = ack_deadline_seconds
        self._subscriber: Any = None
        self._streaming_pull_future: Any = None
        self._is_running = False
        self._semaphore = asyncio.Semaphore(max_concurrent_messages)

    @property
    def subscription_path(self) -> str:
        """Full Pub/Sub subscription path."""
        return f"projects/{self._project_id}/subscriptions/{self._subscription_id}"

    @property
    def is_running(self) -> bool:
        """Whether the connector is actively listening."""
        return self._is_running

    async def start(
        self,
        message_handler: Callable[[dict[str, Any]], Coroutine[Any, Any, Any]],
    ) -> None:
        """
        Start listening for Pub/Sub messages.

        Each message is deserialised and forwarded to the handler callback.
        Messages are processed concurrently up to max_concurrent_messages.

        Args:
            message_handler: Async callback to process each event dict.
        """
        if self._is_running:
            logger.warning("PubSubEventConnector is already running")
            return

        self._is_running = True
        logger.info(
            "Starting Pub/Sub connector: subscription=%s max_concurrent=%d",
            self.subscription_path,
            self._max_concurrent,
        )

        try:
            from google.cloud.pubsub_v1 import SubscriberClient
            from google.cloud.pubsub_v1.types import FlowControl

            self._subscriber = SubscriberClient()

            flow_control = FlowControl(
                max_messages=self._max_concurrent,
                max_bytes=10 * 1024 * 1024,  # 10 MB
            )

            def sync_callback(message: Any) -> None:
                """Synchronous callback wrapper for async handler."""
                try:
                    data = json.loads(message.data.decode("utf-8"))
                    # Merge message attributes into event data
                    attrs = dict(message.attributes) if message.attributes else {}
                    data.setdefault("source", attrs.get("source", "UCP"))
                    data.setdefault("event_type", attrs.get("event_type", ""))
                    data.setdefault("tenant_id", attrs.get("tenant_id", ""))

                    # Run the async handler in the event loop
                    loop = asyncio.get_event_loop()
                    future = asyncio.run_coroutine_threadsafe(
                        self._process_with_semaphore(message_handler, data),
                        loop,
                    )
                    future.result(timeout=self._ack_deadline)
                    message.ack()
                    logger.debug("Message acknowledged: id=%s", message.message_id)
                except json.JSONDecodeError as exc:
                    logger.error(
                        "Failed to deserialise message: id=%s error=%s",
                        message.message_id,
                        exc,
                    )
                    message.nack()
                except Exception as exc:
                    logger.error(
                        "Message processing failed: id=%s error=%s",
                        message.message_id,
                        exc,
                    )
                    message.nack()

            self._streaming_pull_future = self._subscriber.subscribe(
                self.subscription_path,
                callback=sync_callback,
                flow_control=flow_control,
            )

            logger.info("Pub/Sub connector started: subscription=%s", self.subscription_path)

        except ImportError:
            logger.warning(
                "google-cloud-pubsub not available; connector will operate in simulation mode"
            )
            self._is_running = True

    async def _process_with_semaphore(
        self,
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, Any]],
        data: dict[str, Any],
    ) -> None:
        """Process a message with concurrency limiting via semaphore."""
        async with self._semaphore:
            await handler(data)

    async def stop(self) -> None:
        """Stop listening for Pub/Sub messages and clean up resources."""
        if not self._is_running:
            return

        self._is_running = False

        if self._streaming_pull_future is not None:
            self._streaming_pull_future.cancel()
            self._streaming_pull_future = None

        if self._subscriber is not None:
            self._subscriber.close()
            self._subscriber = None

        logger.info("Pub/Sub connector stopped: subscription=%s", self.subscription_path)

    async def process_single_message(
        self,
        raw_message: dict[str, Any],
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, Any]],
    ) -> bool:
        """
        Process a single message directly (for testing or manual replay).

        Args:
            raw_message: Raw message dictionary.
            handler: Async callback to process the event.

        Returns:
            True if processing succeeded.
        """
        try:
            await handler(raw_message)
            return True
        except Exception as exc:
            logger.error("Single message processing failed: error=%s", exc)
            return False
