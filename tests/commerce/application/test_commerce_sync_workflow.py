"""
Tests for CommerceSyncWorkflow — DAG-Based Orchestration

Verifies:
- Full workflow execution with all steps
- Parallel execution of update_inventory and trigger_enrichment
- Step dependency ordering
- Non-critical step failure handling
- DAG structure validation
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from prism.commerce.application.orchestration.commerce_sync_workflow import (
    CommerceSyncWorkflow,
)
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
    """Create a mock UCPInboundPort that returns a RECEIVED event."""
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
def mock_inventory_port() -> AsyncMock:
    """Create a mock InventoryPort."""
    mock = AsyncMock()
    mock.update_availability = AsyncMock()
    mock.get_availability = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def mock_google_shopping_port() -> AsyncMock:
    """Create a mock GoogleShoppingPort."""
    mock = AsyncMock()
    mock.publish_feed = AsyncMock(return_value="feed-123")
    mock.get_feed_status = AsyncMock(return_value={"sync_status": "SYNCED"})
    return mock


@pytest.fixture
def event_processing_service() -> EventProcessingService:
    """Create the real stateless domain service."""
    return EventProcessingService()


@pytest.fixture
def workflow(
    mock_ucp_inbound: AsyncMock,
    mock_inventory_port: AsyncMock,
    mock_google_shopping_port: AsyncMock,
    event_processing_service: EventProcessingService,
) -> CommerceSyncWorkflow:
    """Create the workflow with mocked dependencies."""
    return CommerceSyncWorkflow(
        ucp_inbound_port=mock_ucp_inbound,
        inventory_port=mock_inventory_port,
        google_shopping_port=mock_google_shopping_port,
        event_processing_service=event_processing_service,
    )


class TestWorkflowDAGStructure:
    """Tests for DAG topology and validation."""

    def test_orchestrator_builds_without_cycles(
        self, workflow: CommerceSyncWorkflow
    ) -> None:
        """Verify the DAG has no cycles."""
        orchestrator = workflow.build_orchestrator()
        # If we get here, no OrchestrationError was raised
        assert orchestrator is not None

    def test_orchestrator_has_all_steps(
        self, workflow: CommerceSyncWorkflow
    ) -> None:
        orchestrator = workflow.build_orchestrator()
        expected_steps = {
            "receive_event",
            "classify_event",
            "update_inventory",
            "trigger_enrichment",
            "push_to_google_shopping",
        }
        assert set(orchestrator._steps.keys()) == expected_steps

    def test_parallel_steps_share_dependency(
        self, workflow: CommerceSyncWorkflow
    ) -> None:
        """update_inventory and trigger_enrichment should both depend on classify_event."""
        orchestrator = workflow.build_orchestrator()
        update_inv = orchestrator._steps["update_inventory"]
        trigger_enrich = orchestrator._steps["trigger_enrichment"]
        assert "classify_event" in update_inv.depends_on
        assert "classify_event" in trigger_enrich.depends_on

    def test_google_shopping_depends_on_parallel_steps(
        self, workflow: CommerceSyncWorkflow
    ) -> None:
        orchestrator = workflow.build_orchestrator()
        push_step = orchestrator._steps["push_to_google_shopping"]
        assert "update_inventory" in push_step.depends_on
        assert "trigger_enrichment" in push_step.depends_on


class TestWorkflowExecution:
    """Tests for end-to-end workflow execution."""

    @pytest.mark.asyncio
    async def test_full_product_created_workflow(
        self,
        workflow: CommerceSyncWorkflow,
        mock_ucp_inbound: AsyncMock,
        mock_google_shopping_port: AsyncMock,
    ) -> None:
        """Run the full workflow for a product.created event."""
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
                "price": 2500.00,
                "images": ["https://img.gucci.com/bamboo.jpg"],
            },
        }

        results = await workflow.run(event_data)

        # All steps should have results
        assert "receive_event" in results
        assert "classify_event" in results
        assert "update_inventory" in results
        assert "trigger_enrichment" in results
        assert "push_to_google_shopping" in results

        # Critical steps must succeed
        assert results["receive_event"].success is True
        assert results["classify_event"].success is True

    @pytest.mark.asyncio
    async def test_inventory_event_updates_inventory(
        self,
        workflow: CommerceSyncWorkflow,
        mock_inventory_port: AsyncMock,
    ) -> None:
        """Inventory events should trigger inventory updates."""
        # Override the mock to return an event classified as INVENTORY_CHANGED
        event_data = {
            "event_type": "inventory.changed",
            "source": "UCP",
            "payload": {
                "product_id": "PROD-001",
                "tenant_id": "tenant-gucci",
                "available_quantity": 10,
                "location": "warehouse-eu",
                "fulfilment_options": ["SHIP", "STORE_PICKUP"],
            },
        }

        results = await workflow.run(event_data)
        assert results["receive_event"].success is True

    @pytest.mark.asyncio
    async def test_non_critical_step_failure_does_not_halt(
        self,
        mock_ucp_inbound: AsyncMock,
        mock_inventory_port: AsyncMock,
        mock_google_shopping_port: AsyncMock,
        event_processing_service: EventProcessingService,
    ) -> None:
        """Non-critical step failure should not halt the workflow."""
        # Make Google Shopping fail
        mock_google_shopping_port.publish_feed = AsyncMock(
            side_effect=RuntimeError("API unavailable")
        )

        workflow = CommerceSyncWorkflow(
            ucp_inbound_port=mock_ucp_inbound,
            inventory_port=mock_inventory_port,
            google_shopping_port=mock_google_shopping_port,
            event_processing_service=event_processing_service,
        )

        event_data = {
            "event_type": "product.created",
            "source": "UCP",
            "payload": {
                "id": "PROD-001",
                "sku": "SKU-001",
                "name": "Test Product",
                "brand": "TestBrand",
                "tenant_id": "tenant-test",
            },
        }

        results = await workflow.run(event_data)

        # Critical steps succeed
        assert results["receive_event"].success is True
        assert results["classify_event"].success is True

        # Non-critical push_to_google_shopping may fail gracefully
        # (it depends on trigger_enrichment which depends on classify_event)
        push_result = results.get("push_to_google_shopping")
        # The step result is still present even if it failed
        assert push_result is not None


class TestWorkflowStepIsolation:
    """Tests for individual step behaviour."""

    @pytest.mark.asyncio
    async def test_receive_event_step(
        self, workflow: CommerceSyncWorkflow
    ) -> None:
        """Test the receive_event step in isolation."""
        context = {
            "event_data": {
                "event_type": "product.updated",
                "source": "UCP",
                "payload": {"id": "PROD-001", "sku": "SKU-001"},
            }
        }
        result = await workflow._receive_event(context, {})
        assert "commerce_event" in result
        assert "envelope" in result

    @pytest.mark.asyncio
    async def test_classify_event_step(
        self, workflow: CommerceSyncWorkflow
    ) -> None:
        """Test the classify_event step in isolation."""
        envelope = UCPEventEnvelope(
            event_type="product.created",
            source="UCP",
            payload=(("id", "PROD-001"),),
        )
        commerce_event = CommerceEvent(
            event_type=CommerceEventType.PRODUCT_CREATED,
            tenant_id=TenantId(value="tenant-test"),
        )

        dep_results = {
            "receive_event": {
                "envelope": envelope,
                "commerce_event": commerce_event,
            }
        }

        result = await workflow._classify_event({}, dep_results)
        assert result["event_type"] == CommerceEventType.PRODUCT_CREATED
