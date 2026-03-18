"""
Tests — Payment Aggregate Root State Machine

Verifies the full Payment lifecycle:
- Creation emits PaymentInitiatedEvent
- Authorisation transitions AUTHORISING -> AUTHORISED
- Capture transitions AUTHORISED -> CAPTURED
- Decline transitions AUTHORISING -> DECLINED
- Refund transitions CAPTURED -> REFUNDED
- Cascade retry transitions DECLINED -> AUTHORISING with new PSP
- Invalid transitions raise ValueError
- Immutability: each operation returns a new instance
"""

from __future__ import annotations

import pytest

from prism.shared.domain.value_objects import Currency, Money

from prism.payment.domain.entities.payment import Payment, PaymentStatus, _MAX_RETRIES
from prism.payment.domain.events.payment_events import (
    PaymentAuthorisedEvent,
    PaymentCapturedEvent,
    PaymentDeclinedEvent,
    PaymentInitiatedEvent,
    PaymentRefundedEvent,
    PaymentRetriedEvent,
)
from prism.payment.domain.value_objects.routing import RoutingDecision


# -- Fixtures ------------------------------------------------------------

def _make_payment(**overrides) -> Payment:
    """Create a test payment with sensible defaults."""
    defaults = dict(
        order_id="order-001",
        tenant_id="tenant-luxury-brand",
        amount=Money(amount=1500.00, currency=Currency.EUR),
        customer_currency=Currency.USD,
        settlement_currency=Currency.EUR,
    )
    defaults.update(overrides)
    return Payment.create(**defaults)


def _routing_decision(**overrides) -> RoutingDecision:
    defaults = dict(
        selected_psp="stripe",
        reason="Test routing",
        alternatives=("planet_payment", "adyen"),
        score=0.95,
    )
    defaults.update(overrides)
    return RoutingDecision(**defaults)


# -- Creation tests ------------------------------------------------------

class TestPaymentCreation:
    def test_create_emits_initiated_event(self) -> None:
        payment = _make_payment()

        assert payment.status == PaymentStatus.PENDING
        assert payment.order_id == "order-001"
        assert payment.tenant_id == "tenant-luxury-brand"
        assert payment.amount == Money(amount=1500.00, currency=Currency.EUR)
        assert len(payment.domain_events) == 1
        assert isinstance(payment.domain_events[0], PaymentInitiatedEvent)

    def test_create_event_carries_correct_data(self) -> None:
        payment = _make_payment()
        event = payment.domain_events[0]

        assert isinstance(event, PaymentInitiatedEvent)
        assert event.order_id == "order-001"
        assert event.tenant_id == "tenant-luxury-brand"
        assert event.amount == 1500.00
        assert event.currency == "EUR"

    def test_create_returns_frozen_instance(self) -> None:
        payment = _make_payment()
        with pytest.raises(AttributeError):
            payment.status = PaymentStatus.AUTHORISED  # type: ignore[misc]


# -- Authorisation tests -------------------------------------------------

class TestPaymentAuthorisation:
    def test_begin_authorisation_transitions_to_authorising(self) -> None:
        payment = _make_payment()
        decision = _routing_decision()

        authorising = payment.begin_authorisation(decision)

        assert authorising.status == PaymentStatus.AUTHORISING
        assert authorising.psp_id == "stripe"
        assert authorising.routing_decision == decision
        # Original is unchanged (immutability)
        assert payment.status == PaymentStatus.PENDING

    def test_authorise_transitions_to_authorised(self) -> None:
        payment = _make_payment().begin_authorisation(_routing_decision())

        psp_result = {"transaction_id": "pi_abc123", "status": "authorised"}
        authorised = payment.authorise(psp_result)

        assert authorised.status == PaymentStatus.AUTHORISED
        assert authorised.psp_transaction_id == "pi_abc123"
        events = [e for e in authorised.domain_events if isinstance(e, PaymentAuthorisedEvent)]
        assert len(events) == 1
        assert events[0].psp_transaction_id == "pi_abc123"

    def test_authorise_from_wrong_status_raises(self) -> None:
        payment = _make_payment()  # PENDING, not AUTHORISING
        with pytest.raises(ValueError, match="Cannot authorise"):
            payment.authorise({"transaction_id": "pi_abc123"})


# -- Capture tests -------------------------------------------------------

class TestPaymentCapture:
    def test_capture_transitions_to_captured(self) -> None:
        payment = (
            _make_payment()
            .begin_authorisation(_routing_decision())
            .authorise({"transaction_id": "pi_abc123"})
        )

        captured = payment.capture()

        assert captured.status == PaymentStatus.CAPTURED
        events = [e for e in captured.domain_events if isinstance(e, PaymentCapturedEvent)]
        assert len(events) == 1

    def test_capture_from_pending_raises(self) -> None:
        payment = _make_payment()
        with pytest.raises(ValueError, match="Cannot capture"):
            payment.capture()


# -- Decline tests -------------------------------------------------------

class TestPaymentDecline:
    def test_decline_transitions_to_declined(self) -> None:
        payment = _make_payment().begin_authorisation(_routing_decision())

        declined = payment.decline("insufficient_funds")

        assert declined.status == PaymentStatus.DECLINED
        assert declined.decline_reason == "insufficient_funds"
        events = [e for e in declined.domain_events if isinstance(e, PaymentDeclinedEvent)]
        assert len(events) == 1
        assert events[0].decline_reason == "insufficient_funds"

    def test_decline_from_wrong_status_raises(self) -> None:
        payment = _make_payment()
        with pytest.raises(ValueError, match="Cannot decline"):
            payment.decline("insufficient_funds")


# -- Refund tests --------------------------------------------------------

class TestPaymentRefund:
    def test_refund_transitions_to_refunded(self) -> None:
        payment = (
            _make_payment()
            .begin_authorisation(_routing_decision())
            .authorise({"transaction_id": "pi_abc123"})
            .capture()
        )

        refunded = payment.refund()

        assert refunded.status == PaymentStatus.REFUNDED
        events = [e for e in refunded.domain_events if isinstance(e, PaymentRefundedEvent)]
        assert len(events) == 1
        assert events[0].refund_amount == 1500.00

    def test_refund_from_authorised_raises(self) -> None:
        payment = (
            _make_payment()
            .begin_authorisation(_routing_decision())
            .authorise({"transaction_id": "pi_abc123"})
        )
        with pytest.raises(ValueError, match="Cannot refund"):
            payment.refund()


# -- Cascade retry tests -------------------------------------------------

class TestPaymentCascadeRetry:
    def test_retry_transitions_to_authorising_with_new_psp(self) -> None:
        payment = (
            _make_payment()
            .begin_authorisation(_routing_decision())
            .decline("insufficient_funds")
        )

        retried = payment.retry_with_cascade("planet_payment")

        assert retried.status == PaymentStatus.AUTHORISING
        assert retried.psp_id == "planet_payment"
        assert retried.retry_count == 1
        assert retried.decline_reason is None
        events = [e for e in retried.domain_events if isinstance(e, PaymentRetriedEvent)]
        assert len(events) == 1
        assert events[0].next_psp == "planet_payment"

    def test_retry_exhausted_transitions_to_failed(self) -> None:
        """After _MAX_RETRIES retries, the payment transitions to FAILED."""
        payment = _make_payment().begin_authorisation(_routing_decision())

        # Exhaust all retries
        for i in range(_MAX_RETRIES):
            payment = payment.decline("processor_declined")
            payment = payment.retry_with_cascade("planet_payment")

        # One more decline + retry should fail
        payment = payment.decline("processor_declined")
        failed = payment.retry_with_cascade("planet_payment")

        assert failed.status == PaymentStatus.FAILED

    def test_retry_from_wrong_status_raises(self) -> None:
        payment = _make_payment()
        with pytest.raises(ValueError, match="Cannot retry_with_cascade"):
            payment.retry_with_cascade("planet_payment")


# -- FX rate attachment --------------------------------------------------

class TestPaymentFXRate:
    def test_attach_fx_rate(self) -> None:
        from datetime import UTC, datetime, timedelta

        from prism.payment.domain.value_objects.fx import FXRate

        payment = _make_payment()
        now = datetime.now(UTC)
        rate = FXRate(
            source_currency=Currency.USD,
            target_currency=Currency.EUR,
            rate=0.92,
            provider="ecb",
            quoted_at=now,
            expires_at=now + timedelta(minutes=5),
        )

        with_rate = payment.with_fx_rate(rate)

        assert with_rate.fx_rate == rate
        assert payment.fx_rate is None  # Original unchanged


# -- Event accumulation --------------------------------------------------

class TestPaymentEventAccumulation:
    def test_full_lifecycle_accumulates_events(self) -> None:
        """A complete happy-path lifecycle should accumulate the correct events."""
        payment = (
            _make_payment()
            .begin_authorisation(_routing_decision())
            .authorise({"transaction_id": "pi_abc123"})
            .capture()
        )

        event_types = [type(e).__name__ for e in payment.domain_events]
        assert event_types == [
            "PaymentInitiatedEvent",
            "PaymentAuthorisedEvent",
            "PaymentCapturedEvent",
        ]

    def test_clear_events(self) -> None:
        payment = _make_payment()
        assert len(payment.domain_events) == 1

        cleared = payment.clear_events()
        assert len(cleared.domain_events) == 0
