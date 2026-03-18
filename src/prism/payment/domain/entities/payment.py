"""
Payment Domain — Payment Aggregate Root

Architectural Intent:
- Central aggregate for payment lifecycle management
- Frozen dataclass enforces immutability; every mutation returns a new instance
- State machine transitions (authorise, capture, decline, refund, retry) are
  guarded by preconditions and emit domain events
- RoutingDecision and FXRate are attached for full audit trail
- retry_with_cascade implements FlowRoute's cascade failover pattern

State Machine:
  PENDING -> AUTHORISING -> AUTHORISED -> CAPTURING -> CAPTURED
                         -> DECLINED -> (retry) AUTHORISING
                                     -> FAILED
  CAPTURED -> REFUNDED
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from prism.shared.domain.entities import AggregateRoot
from prism.shared.domain.value_objects import Currency, Money

from prism.payment.domain.events.payment_events import (
    PaymentAuthorisedEvent,
    PaymentCapturedEvent,
    PaymentDeclinedEvent,
    PaymentInitiatedEvent,
    PaymentRefundedEvent,
    PaymentRetriedEvent,
)
from prism.payment.domain.value_objects.fx import FXRate
from prism.payment.domain.value_objects.routing import RoutingDecision


class PaymentStatus(str, Enum):
    """Payment lifecycle states."""

    PENDING = "PENDING"
    AUTHORISING = "AUTHORISING"
    AUTHORISED = "AUTHORISED"
    CAPTURING = "CAPTURING"
    CAPTURED = "CAPTURED"
    DECLINED = "DECLINED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


# Maximum cascade retry attempts before marking as FAILED
_MAX_RETRIES = 3


@dataclass(frozen=True)
class Payment(AggregateRoot):
    """
    Payment aggregate root — owns the full payment lifecycle.

    Every state-changing method returns a new Payment instance with the
    appropriate domain event attached. The application layer persists the
    new instance and dispatches events post-commit.
    """

    order_id: str = ""
    tenant_id: str = ""
    amount: Money = field(default_factory=lambda: Money(amount=0.0, currency=Currency.USD))
    customer_currency: Currency = Currency.USD
    settlement_currency: Currency = Currency.USD
    status: PaymentStatus = PaymentStatus.PENDING
    psp_id: str = ""
    psp_transaction_id: str = ""
    routing_decision: RoutingDecision | None = None
    fx_rate: FXRate | None = None
    retry_count: int = 0
    decline_reason: str | None = None

    # -- Factory ----------------------------------------------------------

    @classmethod
    def create(
        cls,
        order_id: str,
        tenant_id: str,
        amount: Money,
        customer_currency: Currency,
        settlement_currency: Currency,
    ) -> Payment:
        """
        Create a new Payment in PENDING status.

        Returns the Payment with a PaymentInitiatedEvent attached.
        """
        payment = cls(
            order_id=order_id,
            tenant_id=tenant_id,
            amount=amount,
            customer_currency=customer_currency,
            settlement_currency=settlement_currency,
            status=PaymentStatus.PENDING,
        )
        event = PaymentInitiatedEvent(
            aggregate_id=payment.id,
            tenant_id=tenant_id,
            order_id=order_id,
            amount=amount.amount,
            currency=amount.currency.value,
            customer_currency=customer_currency.value,
        )
        return replace(
            payment,
            domain_events=payment.domain_events + (event,),
        )

    # -- State transitions ------------------------------------------------

    def begin_authorisation(self, routing_decision: RoutingDecision) -> Payment:
        """Transition to AUTHORISING with the selected PSP routing decision."""
        self._assert_status(PaymentStatus.PENDING, "begin_authorisation")
        return replace(
            self,
            status=PaymentStatus.AUTHORISING,
            psp_id=routing_decision.selected_psp,
            routing_decision=routing_decision,
            **self._touch(),
        )

    def authorise(self, psp_result: dict[str, Any]) -> Payment:
        """
        Transition to AUTHORISED after a successful PSP authorisation.

        ``psp_result`` must contain ``transaction_id`` from the PSP.
        """
        self._assert_status(PaymentStatus.AUTHORISING, "authorise")
        transaction_id = psp_result.get("transaction_id", "")
        event = PaymentAuthorisedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            psp_id=self.psp_id,
            psp_transaction_id=transaction_id,
            amount=self.amount.amount,
            currency=self.amount.currency.value,
        )
        return replace(
            self,
            status=PaymentStatus.AUTHORISED,
            psp_transaction_id=transaction_id,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def capture(self) -> Payment:
        """
        Transition from AUTHORISED -> CAPTURING -> CAPTURED.

        In production, CAPTURING is transient during the PSP call; here
        we move directly to CAPTURED as the infrastructure layer handles
        the async PSP interaction.
        """
        self._assert_status(PaymentStatus.AUTHORISED, "capture")
        event = PaymentCapturedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            psp_id=self.psp_id,
            psp_transaction_id=self.psp_transaction_id,
            amount=self.amount.amount,
            currency=self.amount.currency.value,
        )
        return replace(
            self,
            status=PaymentStatus.CAPTURED,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def decline(self, reason: str) -> Payment:
        """
        Transition to DECLINED when the PSP refuses the authorisation.

        The ``reason`` is stored for cascade retry evaluation and analytics.
        """
        self._assert_status(PaymentStatus.AUTHORISING, "decline")
        event = PaymentDeclinedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            psp_id=self.psp_id,
            decline_reason=reason,
            retry_count=self.retry_count,
        )
        return replace(
            self,
            status=PaymentStatus.DECLINED,
            decline_reason=reason,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def refund(self) -> Payment:
        """
        Transition to REFUNDED from a CAPTURED payment.

        Full refund only — partial refunds are handled via a separate workflow.
        """
        self._assert_status(PaymentStatus.CAPTURED, "refund")
        event = PaymentRefundedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            psp_id=self.psp_id,
            psp_transaction_id=self.psp_transaction_id,
            refund_amount=self.amount.amount,
            currency=self.amount.currency.value,
        )
        return replace(
            self,
            status=PaymentStatus.REFUNDED,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def retry_with_cascade(self, next_psp: str) -> Payment:
        """
        Re-enter AUTHORISING with a different PSP after a decline.

        Increments the retry counter and updates the PSP assignment.
        If the retry budget is exhausted, transitions to FAILED instead.
        """
        self._assert_status(PaymentStatus.DECLINED, "retry_with_cascade")
        new_retry_count = self.retry_count + 1

        if new_retry_count > _MAX_RETRIES:
            return replace(
                self,
                status=PaymentStatus.FAILED,
                **self._touch(),
            )

        event = PaymentRetriedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id,
            order_id=self.order_id,
            previous_psp=self.psp_id,
            next_psp=next_psp,
            retry_count=new_retry_count,
            decline_reason=self.decline_reason or "",
        )
        # Build a new RoutingDecision for the cascade PSP
        cascade_decision = RoutingDecision(
            selected_psp=next_psp,
            reason=f"Cascade retry #{new_retry_count} after decline: {self.decline_reason}",
            alternatives=tuple(
                alt
                for alt in (self.routing_decision.alternatives if self.routing_decision else ())
                if alt != next_psp
            ),
            score=0.0,
        )
        return replace(
            self,
            status=PaymentStatus.AUTHORISING,
            psp_id=next_psp,
            psp_transaction_id="",
            routing_decision=cascade_decision,
            retry_count=new_retry_count,
            decline_reason=None,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def with_fx_rate(self, rate: FXRate) -> Payment:
        """Attach an FX rate to this payment (returns new instance)."""
        return replace(self, fx_rate=rate, **self._touch())

    # -- Guards -----------------------------------------------------------

    def _assert_status(self, expected: PaymentStatus, operation: str) -> None:
        if self.status != expected:
            raise ValueError(
                f"Cannot {operation}: payment is {self.status.value}, "
                f"expected {expected.value}"
            )
