"""
Commerce Application Command — Process UCP Event

Architectural Intent:
- Use case for receiving and processing a raw UCP event
- Orchestrates: receive -> classify -> persist -> trigger downstream processing
- Publishes domain events after successful persistence
- Returns CommandResult for consistent success/failure semantics
- Infrastructure dependencies injected via ports (no direct adapter coupling)

Flow:
  1. Convert DTO to UCPEventEnvelope
  2. Receive event via UCPInboundPort (persist in RECEIVED status)
  3. Classify event type via domain service
  4. Transition to PROCESSING -> PROCESSED
  5. Publish collected domain events via event bus
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from prism.commerce.domain.entities.commerce_event import CommerceEvent
from prism.commerce.domain.ports.commerce_ports import UCPInboundPort
from prism.commerce.domain.services.event_processing_service import (
    EventProcessingService,
)
from prism.commerce.domain.value_objects.ucp_schema import UCPEventEnvelope
from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort


class ProcessUCPEventUseCase:
    """
    Receives a raw UCP event, classifies it, persists it, and triggers
    downstream processing.

    This is the primary entry point for all inbound UCP events. It coordinates
    the domain service (classification) with the infrastructure port (persistence)
    and the event bus (downstream notifications).
    """

    def __init__(
        self,
        ucp_inbound_port: UCPInboundPort,
        event_processing_service: EventProcessingService,
        event_bus: EventBusPort,
    ) -> None:
        self._ucp_inbound = ucp_inbound_port
        self._event_service = event_processing_service
        self._event_bus = event_bus

    async def execute(
        self, event_data: dict[str, Any]
    ) -> CommandResult[CommerceEvent]:
        """
        Process a raw UCP event from its dictionary representation.

        Args:
            event_data: Raw UCP event data (typically from Pub/Sub or API).

        Returns:
            CommandResult containing the processed CommerceEvent on success,
            or an error description on failure.
        """
        try:
            # 1. Build envelope from raw data
            envelope = UCPEventEnvelope.from_dict(event_data)

            # 2. Classify the event type
            event_type = self._event_service.classify_event(envelope)

            # 3. Receive and persist via inbound port
            commerce_event = await self._ucp_inbound.receive_event(envelope)

            # 4. Transition through processing states
            commerce_event = commerce_event.mark_processing()
            commerce_event = commerce_event.mark_processed()

            # 5. Dispatch domain events
            if commerce_event.domain_events:
                await self._event_bus.publish(list(commerce_event.domain_events))
                commerce_event = commerce_event.clear_events()

            return CommandResult.ok(commerce_event)

        except ValueError as exc:
            return CommandResult.fail(
                error=f"Validation error: {exc}",
                code="VALIDATION_ERROR",
            )
        except Exception as exc:
            return CommandResult.fail(
                error=f"Processing failed: {exc}",
                code="PROCESSING_ERROR",
            )
