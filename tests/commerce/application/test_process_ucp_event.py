"""
Tests for ProcessUCPEventUseCase

Verifies:
- Successful end-to-end event processing
- Domain event publication after processing
- Validation error handling (missing event_type)
- Processing error handling
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from prism.commerce.application.commands.process_ucp_event import ProcessUCPEventUseCase
from prism.commerce.domain.entities.commerce_event import (
    CommerceEvent,
    CommerceEventSource,
    CommerceEventType,
    ProcessingStatus,
)
from prism.commerce.domain.services.event_processing_service import EventProcessingService
from prism.commerce.domain.value_objects.ucp_schema import UCPEventEnvelope
from prism.shared.domain.value_objects import TenantId


@pytest.fixture
def mock_ucp_inbound() -> AsyncMock:
    """Create a mock UCPInboundPort."""
    mock = AsyncMock()
    mock.receive_event = AsyncMock(
        return_value=CommerceEvent(
            event_type=CommerceEventType.PRODUCT_CREATED,
            source=CommerceEventSource.UCP,
            tenant_id=TenantId(value="tenant-gucci"),
            processing_status=ProcessingStatus.RECEIVED,
        )
    )
    return mock


@pytest.fixture
def mock_event_bus() -> AsyncMock:
    """Create a mock EventBusPort."""
    mock = AsyncMock()
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def event_processing_service() -> EventProcessingService:
    """Create the real domain service (it is stateless)."""
    return EventProcessingService()


@pytest.fixture
def use_case(
    mock_ucp_inbound: AsyncMock,
    event_processing_service: EventProcessingService,
    mock_event_bus: AsyncMock,
) -> ProcessUCPEventUseCase:
    """Create the use case with mocked dependencies."""
    return ProcessUCPEventUseCase(
        ucp_inbound_port=mock_ucp_inbound,
        event_processing_service=event_processing_service,
        event_bus=mock_event_bus,
    )


class TestProcessUCPEventSuccess:
    """Tests for successful event processing."""

    @pytest.mark.asyncio
    async def test_process_product_created_event(
        self, use_case: ProcessUCPEventUseCase, mock_event_bus: AsyncMock
    ) -> None:
        event_data = {
            "event_id": "evt-001",
            "event_type": "product.created",
            "source": "UCP",
            "payload": {
                "id": "PROD-001",
                "sku": "GUC-BAG-001",
                "name": "Bamboo Bag",
                "brand": "Gucci",
                "tenant_id": "tenant-gucci",
            },
        }

        result = await use_case.execute(event_data)

        assert result.success is True
        assert result.value is not None
        assert result.value.processing_status == ProcessingStatus.PROCESSED
        mock_event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_inventory_changed_event(
        self, use_case: ProcessUCPEventUseCase
    ) -> None:
        event_data = {
            "event_type": "inventory.changed",
            "source": "UCP",
            "payload": {
                "product_id": "PROD-001",
                "available_quantity": 5,
                "location": "warehouse-eu",
            },
        }

        result = await use_case.execute(event_data)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_domain_events_dispatched(
        self, use_case: ProcessUCPEventUseCase, mock_event_bus: AsyncMock
    ) -> None:
        event_data = {
            "event_type": "product.updated",
            "source": "UCP",
            "payload": {"id": "PROD-001", "sku": "SKU-001"},
        }

        result = await use_case.execute(event_data)
        assert result.success is True

        # Verify domain events were published
        mock_event_bus.publish.assert_called_once()
        published_events = mock_event_bus.publish.call_args[0][0]
        assert len(published_events) > 0

    @pytest.mark.asyncio
    async def test_events_cleared_after_dispatch(
        self, use_case: ProcessUCPEventUseCase
    ) -> None:
        event_data = {
            "event_type": "price.changed",
            "source": "UCP",
            "payload": {"id": "PROD-001", "sku": "SKU-001", "price": 999.99},
        }

        result = await use_case.execute(event_data)
        assert result.success is True
        assert result.value is not None
        # Events should be cleared after dispatch
        assert result.value.domain_events == ()


class TestProcessUCPEventValidation:
    """Tests for validation and error handling."""

    @pytest.mark.asyncio
    async def test_missing_event_type_fails(
        self, use_case: ProcessUCPEventUseCase
    ) -> None:
        event_data = {
            "event_type": "",
            "source": "UCP",
            "payload": {},
        }

        result = await use_case.execute(event_data)
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"

    @pytest.mark.asyncio
    async def test_missing_payload_uses_defaults(
        self, use_case: ProcessUCPEventUseCase
    ) -> None:
        event_data = {
            "event_type": "product.created",
            "source": "UCP",
        }

        result = await use_case.execute(event_data)
        assert result.success is True


class TestProcessUCPEventInfraFailure:
    """Tests for infrastructure failure handling."""

    @pytest.mark.asyncio
    async def test_inbound_port_failure(
        self,
        event_processing_service: EventProcessingService,
        mock_event_bus: AsyncMock,
    ) -> None:
        failing_port = AsyncMock()
        failing_port.receive_event = AsyncMock(
            side_effect=RuntimeError("Database unavailable")
        )

        use_case = ProcessUCPEventUseCase(
            ucp_inbound_port=failing_port,
            event_processing_service=event_processing_service,
            event_bus=mock_event_bus,
        )

        event_data = {
            "event_type": "product.created",
            "source": "UCP",
            "payload": {"id": "PROD-001", "sku": "SKU-001"},
        }

        result = await use_case.execute(event_data)
        assert result.success is False
        assert result.error_code == "PROCESSING_ERROR"
        assert "Database unavailable" in (result.error or "")
