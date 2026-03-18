"""
Try-On Domain — TryOnSession Aggregate Root

Architectural Intent:
- Central aggregate for the virtual try-on workflow
- Enforces state machine transitions: PENDING -> PROCESSING -> COMPOSITING -> COMPLETED | FAILED
- Frozen dataclass: all mutations return new instances via dataclasses.replace()
- Domain events are accumulated on each transition for downstream dispatch

Privacy-by-design (GDPR):
- NO customer image field is stored on this entity
- Customer image bytes are passed through the processing pipeline in-memory only
- The session tracks product references and processing metrics, never customer data

State Machine:
  PENDING ──start_processing()──> PROCESSING
  PROCESSING ──complete_body_extraction()──> COMPOSITING
  COMPOSITING ──complete_composition()──> COMPLETED
  Any ──fail()──> FAILED
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from prism.shared.domain.entities import AggregateRoot

from prism.tryon.domain.events.tryon_events import (
    TryOnCompletedEvent,
    TryOnFailedEvent,
    TryOnStartedEvent,
)
from prism.tryon.domain.value_objects.composition import (
    BodyPose,
    BrandTryOnConfig,
    TryOnComposition,
)


class TryOnCategory(str, Enum):
    """Product categories that support virtual try-on."""

    APPAREL = "APPAREL"
    ACCESSORIES = "ACCESSORIES"
    EYEWEAR = "EYEWEAR"
    JEWELLERY = "JEWELLERY"


class TryOnStatus(str, Enum):
    """Lifecycle states of a try-on session."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPOSITING = "COMPOSITING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class TryOnSession(AggregateRoot):
    """
    Aggregate root for a single virtual try-on session.

    Tracks the lifecycle of a try-on request from initiation through
    body extraction, composition, and final delivery. Customer image
    data is deliberately excluded — it is processed in-memory by the
    application pipeline and never persisted.

    Attributes:
        session_id: Alias for the inherited ``id`` field (aggregate identity).
        tenant_id: Brand/tenant scope for multi-tenant isolation.
        product_id: The product being virtually tried on.
        category: Product category (APPAREL, ACCESSORIES, EYEWEAR, JEWELLERY).
        status: Current lifecycle state of the session.
        composition_result: The final try-on composition (set on COMPLETED).
        processing_time_ms: Total pipeline processing time in milliseconds.
        brand_config: Tenant-specific rendering configuration.
    """

    session_id: str = ""
    tenant_id: str = ""
    product_id: str = ""
    category: TryOnCategory = TryOnCategory.APPAREL
    status: TryOnStatus = TryOnStatus.PENDING
    composition_result: TryOnComposition | None = None
    processing_time_ms: int = 0
    brand_config: BrandTryOnConfig = field(default_factory=BrandTryOnConfig)

    # --- State machine transitions ---

    def start_processing(self) -> TryOnSession:
        """
        Transition from PENDING to PROCESSING.

        Emits a TryOnStartedEvent for latency tracking and resource monitoring.

        Raises:
            InvalidStateTransitionError: If the session is not in PENDING status.
        """
        self._assert_status(TryOnStatus.PENDING, "start_processing")

        event = TryOnStartedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id,
            session_id=self.session_id or self.id,
            product_id=self.product_id,
            category=self.category.value,
        )

        updated = replace(
            self,
            status=TryOnStatus.PROCESSING,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=updated.domain_events + (event,),
        )

    def complete_body_extraction(self, pose_data: BodyPose) -> TryOnSession:
        """
        Transition from PROCESSING to COMPOSITING after pose extraction.

        The pose_data is validated but note that the raw customer image bytes
        have already been discarded by this point in the pipeline.

        Args:
            pose_data: Extracted body pose keypoints.

        Raises:
            InvalidStateTransitionError: If the session is not in PROCESSING status.
            ValueError: If pose_data has no keypoints.
        """
        self._assert_status(TryOnStatus.PROCESSING, "complete_body_extraction")

        if not pose_data.keypoints:
            raise ValueError("Body extraction produced no keypoints")

        return replace(
            self,
            status=TryOnStatus.COMPOSITING,
            **self._touch(),
        )

    def complete_composition(
        self,
        result: TryOnComposition,
        processing_time_ms: int = 0,
    ) -> TryOnSession:
        """
        Transition from COMPOSITING to COMPLETED with the final result.

        Emits a TryOnCompletedEvent carrying performance metrics and the
        result reference (signed URL).

        Args:
            result: The composited try-on result.
            processing_time_ms: Total end-to-end processing time.

        Raises:
            InvalidStateTransitionError: If the session is not in COMPOSITING status.
        """
        self._assert_status(TryOnStatus.COMPOSITING, "complete_composition")

        event = TryOnCompletedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id,
            session_id=self.session_id or self.id,
            product_id=self.product_id,
            processing_time_ms=processing_time_ms,
            confidence=result.confidence,
            result_image_url=result.result_image_url,
        )

        updated = replace(
            self,
            status=TryOnStatus.COMPLETED,
            composition_result=result,
            processing_time_ms=processing_time_ms,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=updated.domain_events + (event,),
        )

    def fail(self, reason: str, processing_time_ms: int = 0) -> TryOnSession:
        """
        Transition any non-terminal state to FAILED.

        Emits a TryOnFailedEvent for alerting and diagnostics.

        Args:
            reason: Human-readable failure reason.
            processing_time_ms: Processing time before failure.

        Raises:
            InvalidStateTransitionError: If the session is already COMPLETED or FAILED.
        """
        if self.status in (TryOnStatus.COMPLETED, TryOnStatus.FAILED):
            raise InvalidStateTransitionError(
                f"Cannot fail session in {self.status.value} status"
            )

        event = TryOnFailedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id,
            session_id=self.session_id or self.id,
            product_id=self.product_id,
            reason=reason,
            processing_time_ms=processing_time_ms,
        )

        updated = replace(
            self,
            status=TryOnStatus.FAILED,
            processing_time_ms=processing_time_ms,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=updated.domain_events + (event,),
        )

    # --- Internal helpers ---

    def _assert_status(self, expected: TryOnStatus, operation: str) -> None:
        """Raise if the session is not in the expected status."""
        if self.status != expected:
            raise InvalidStateTransitionError(
                f"Cannot {operation}: session is {self.status.value}, "
                f"expected {expected.value}"
            )


class InvalidStateTransitionError(Exception):
    """Raised when a TryOnSession state transition is invalid."""
