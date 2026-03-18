"""
Tests for TryOnSession Aggregate Root

Tests cover:
- State machine transitions (happy path and invalid transitions)
- Domain event emission on each transition
- GDPR compliance: no customer image field exists on the entity
- Immutability: all mutations return new instances
- Validation: empty keypoints rejected, terminal states cannot transition
"""

from __future__ import annotations

import pytest

from prism.tryon.domain.entities.tryon_session import (
    InvalidStateTransitionError,
    TryOnCategory,
    TryOnSession,
    TryOnStatus,
)
from prism.tryon.domain.events.tryon_events import (
    TryOnCompletedEvent,
    TryOnFailedEvent,
    TryOnStartedEvent,
)
from prism.tryon.domain.value_objects.composition import (
    BodyPose,
    BrandTryOnConfig,
    ProductOverlay,
    TryOnComposition,
)


# --- Fixtures ---


def _make_session(**overrides) -> TryOnSession:
    """Create a TryOnSession with sensible defaults."""
    defaults = {
        "tenant_id": "tenant-gucci",
        "product_id": "product-123",
        "category": TryOnCategory.APPAREL,
    }
    defaults.update(overrides)
    return TryOnSession(**defaults)


def _make_pose(**overrides) -> BodyPose:
    """Create a BodyPose with sample keypoints."""
    defaults = {
        "keypoints": {
            "left_shoulder": (0.3, 0.4, 0.95),
            "right_shoulder": (0.7, 0.4, 0.93),
            "left_hip": (0.35, 0.65, 0.91),
            "right_hip": (0.65, 0.65, 0.90),
            "neck": (0.5, 0.3, 0.97),
        },
        "orientation": "front",
        "body_type": "standard",
    }
    defaults.update(overrides)
    return BodyPose(**defaults)


def _make_composition(**overrides) -> TryOnComposition:
    """Create a TryOnComposition with sensible defaults."""
    defaults = {
        "result_image_url": "https://storage.googleapis.com/signed-url/result.png",
        "confidence": 0.92,
        "body_pose": _make_pose(),
        "product_overlay": ProductOverlay(product_id="product-123"),
    }
    defaults.update(overrides)
    return TryOnComposition(**defaults)


# --- GDPR Compliance ---


class TestGDPRCompliance:
    """Verify that TryOnSession never stores customer image data."""

    def test_no_customer_image_field(self):
        """TryOnSession must not have any field for customer image data."""
        session = _make_session()
        field_names = {f.name for f in session.__dataclass_fields__.values()}

        # Explicitly assert no image-related fields exist
        image_field_patterns = {"customer_image", "image_data", "image_bytes", "photo"}
        assert field_names.isdisjoint(image_field_patterns), (
            f"GDPR violation: TryOnSession contains image fields: "
            f"{field_names & image_field_patterns}"
        )

    def test_session_fields_are_metadata_only(self):
        """All session fields should be identifiers, enums, or processing metadata."""
        session = _make_session()
        # Verify the fields are what we expect (no bytes or raw data)
        assert isinstance(session.tenant_id, str)
        assert isinstance(session.product_id, str)
        assert isinstance(session.category, TryOnCategory)
        assert isinstance(session.status, TryOnStatus)
        assert isinstance(session.processing_time_ms, int)
        assert isinstance(session.brand_config, BrandTryOnConfig)


# --- State Machine: Happy Path ---


class TestStateTransitionsHappyPath:
    """Test the full PENDING -> PROCESSING -> COMPOSITING -> COMPLETED flow."""

    def test_initial_state_is_pending(self):
        session = _make_session()
        assert session.status == TryOnStatus.PENDING
        assert session.composition_result is None
        assert session.processing_time_ms == 0

    def test_start_processing(self):
        session = _make_session()
        updated = session.start_processing()

        assert updated.status == TryOnStatus.PROCESSING
        assert updated is not session  # Immutability: new instance
        assert session.status == TryOnStatus.PENDING  # Original unchanged

    def test_start_processing_emits_event(self):
        session = _make_session()
        updated = session.start_processing()

        assert len(updated.domain_events) == 1
        event = updated.domain_events[0]
        assert isinstance(event, TryOnStartedEvent)
        assert event.product_id == "product-123"
        assert event.tenant_id == "tenant-gucci"
        assert event.category == "APPAREL"

    def test_complete_body_extraction(self):
        session = _make_session().start_processing()
        pose = _make_pose()

        updated = session.complete_body_extraction(pose)
        assert updated.status == TryOnStatus.COMPOSITING

    def test_complete_composition(self):
        session = (
            _make_session()
            .start_processing()
            .complete_body_extraction(_make_pose())
        )
        composition = _make_composition()

        updated = session.complete_composition(composition, processing_time_ms=2500)

        assert updated.status == TryOnStatus.COMPLETED
        assert updated.composition_result is composition
        assert updated.processing_time_ms == 2500

    def test_complete_composition_emits_event(self):
        session = (
            _make_session()
            .start_processing()
            .complete_body_extraction(_make_pose())
        )
        composition = _make_composition()
        updated = session.complete_composition(composition, processing_time_ms=3000)

        # Should have TryOnStartedEvent + TryOnCompletedEvent
        completed_events = [
            e for e in updated.domain_events if isinstance(e, TryOnCompletedEvent)
        ]
        assert len(completed_events) == 1
        event = completed_events[0]
        assert event.processing_time_ms == 3000
        assert event.confidence == 0.92
        assert event.product_id == "product-123"

    def test_full_lifecycle_accumulates_events(self):
        session = _make_session()
        session = session.start_processing()
        session = session.complete_body_extraction(_make_pose())
        session = session.complete_composition(_make_composition(), processing_time_ms=1800)

        # Should accumulate: TryOnStartedEvent + TryOnCompletedEvent
        assert len(session.domain_events) == 2
        assert isinstance(session.domain_events[0], TryOnStartedEvent)
        assert isinstance(session.domain_events[1], TryOnCompletedEvent)


# --- State Machine: Failure Path ---


class TestStateTransitionsFailure:
    """Test failure transitions and invalid state transitions."""

    def test_fail_from_pending(self):
        session = _make_session()
        updated = session.fail("User cancelled", processing_time_ms=0)

        assert updated.status == TryOnStatus.FAILED
        assert updated.processing_time_ms == 0

    def test_fail_from_processing(self):
        session = _make_session().start_processing()
        updated = session.fail("Body extraction timeout", processing_time_ms=5000)

        assert updated.status == TryOnStatus.FAILED
        assert updated.processing_time_ms == 5000

    def test_fail_from_compositing(self):
        session = (
            _make_session()
            .start_processing()
            .complete_body_extraction(_make_pose())
        )
        updated = session.fail("Imagen API error", processing_time_ms=3000)

        assert updated.status == TryOnStatus.FAILED

    def test_fail_emits_event(self):
        session = _make_session().start_processing()
        updated = session.fail("Timeout", processing_time_ms=4500)

        failed_events = [
            e for e in updated.domain_events if isinstance(e, TryOnFailedEvent)
        ]
        assert len(failed_events) == 1
        assert failed_events[0].reason == "Timeout"
        assert failed_events[0].processing_time_ms == 4500

    def test_cannot_fail_completed_session(self):
        session = (
            _make_session()
            .start_processing()
            .complete_body_extraction(_make_pose())
            .complete_composition(_make_composition())
        )
        with pytest.raises(InvalidStateTransitionError, match="COMPLETED"):
            session.fail("Too late")

    def test_cannot_fail_already_failed_session(self):
        session = _make_session().fail("First failure")
        with pytest.raises(InvalidStateTransitionError, match="FAILED"):
            session.fail("Second failure")


# --- State Machine: Invalid Transitions ---


class TestInvalidStateTransitions:
    """Test that invalid state transitions are rejected."""

    def test_cannot_start_processing_twice(self):
        session = _make_session().start_processing()
        with pytest.raises(InvalidStateTransitionError, match="PROCESSING"):
            session.start_processing()

    def test_cannot_complete_extraction_from_pending(self):
        session = _make_session()
        with pytest.raises(InvalidStateTransitionError, match="PENDING"):
            session.complete_body_extraction(_make_pose())

    def test_cannot_complete_composition_from_processing(self):
        session = _make_session().start_processing()
        with pytest.raises(InvalidStateTransitionError, match="PROCESSING"):
            session.complete_composition(_make_composition())

    def test_cannot_complete_composition_from_pending(self):
        session = _make_session()
        with pytest.raises(InvalidStateTransitionError, match="PENDING"):
            session.complete_composition(_make_composition())

    def test_empty_keypoints_rejected(self):
        session = _make_session().start_processing()
        empty_pose = BodyPose(keypoints={}, orientation="front")
        with pytest.raises(ValueError, match="no keypoints"):
            session.complete_body_extraction(empty_pose)


# --- Immutability ---


class TestImmutability:
    """Verify that TryOnSession is truly immutable."""

    def test_frozen_dataclass(self):
        session = _make_session()
        with pytest.raises(AttributeError):
            session.status = TryOnStatus.PROCESSING  # type: ignore[misc]

    def test_transitions_return_new_instances(self):
        s1 = _make_session()
        s2 = s1.start_processing()
        s3 = s2.complete_body_extraction(_make_pose())
        s4 = s3.complete_composition(_make_composition())

        # All different objects
        assert s1 is not s2
        assert s2 is not s3
        assert s3 is not s4

        # Original states preserved
        assert s1.status == TryOnStatus.PENDING
        assert s2.status == TryOnStatus.PROCESSING
        assert s3.status == TryOnStatus.COMPOSITING
        assert s4.status == TryOnStatus.COMPLETED

    def test_clear_events_returns_new_instance(self):
        session = _make_session().start_processing()
        assert len(session.domain_events) == 1

        cleared = session.clear_events()
        assert len(cleared.domain_events) == 0
        assert len(session.domain_events) == 1  # Original unchanged


# --- Value Object Validation ---


class TestValueObjectValidation:
    """Test validation in composition value objects."""

    def test_invalid_orientation_rejected(self):
        with pytest.raises(ValueError, match="Invalid orientation"):
            BodyPose(keypoints={"neck": (0.5, 0.3, 0.9)}, orientation="upside_down")

    def test_negative_scale_rejected(self):
        with pytest.raises(ValueError, match="scale must be positive"):
            ProductOverlay(product_id="p1", scale=-1.0)

    def test_empty_product_id_rejected(self):
        with pytest.raises(ValueError, match="product_id"):
            ProductOverlay(product_id="")

    def test_confidence_out_of_range_rejected(self):
        with pytest.raises(ValueError, match="Confidence"):
            TryOnComposition(confidence=1.5)

    def test_watermark_without_image_rejected(self):
        with pytest.raises(ValueError, match="watermark_image"):
            BrandTryOnConfig(watermark_enabled=True, watermark_image=None)
