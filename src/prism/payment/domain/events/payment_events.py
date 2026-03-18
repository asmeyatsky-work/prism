"""
Payment Domain Events

Architectural Intent:
- Immutable event records emitted on Payment lifecycle state transitions
- Consumed by Commerce (order status), Intelligence (analytics),
  and Reconciliation (BARQ settlement matching)
- All events carry tenant_id for multi-tenant routing (inherited from DomainEvent)
- Carried on AggregateRoot.domain_events and dispatched after persistence

Event Flow:
  Initiate  -> PaymentInitiatedEvent
  Authorise -> PaymentAuthorisedEvent
  Capture   -> PaymentCapturedEvent
  Decline   -> PaymentDeclinedEvent
  Refund    -> PaymentRefundedEvent
  Retry     -> PaymentRetriedEvent
  FX Quote  -> FXRateQuotedEvent
"""

from __future__ import annotations

from dataclasses import dataclass

from prism.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class PaymentInitiatedEvent(DomainEvent):
    """
    Emitted when a new payment is created and routing evaluation begins.

    Triggers FlowRoute's PSP selection and parallel FX rate fetching.
    """

    order_id: str = ""
    amount: float = 0.0
    currency: str = ""
    customer_currency: str = ""


@dataclass(frozen=True)
class PaymentAuthorisedEvent(DomainEvent):
    """
    Emitted when a PSP successfully authorises the payment.

    Downstream consumers can proceed with order fulfilment preparation.
    """

    order_id: str = ""
    psp_id: str = ""
    psp_transaction_id: str = ""
    amount: float = 0.0
    currency: str = ""


@dataclass(frozen=True)
class PaymentCapturedEvent(DomainEvent):
    """
    Emitted when an authorised payment is captured (funds settled).

    Triggers BARQ reconciliation and Commerce order completion.
    """

    order_id: str = ""
    psp_id: str = ""
    psp_transaction_id: str = ""
    amount: float = 0.0
    currency: str = ""


@dataclass(frozen=True)
class PaymentDeclinedEvent(DomainEvent):
    """
    Emitted when a PSP declines the payment authorisation.

    May trigger cascade retry via FlowRoute if retry budget remains.
    """

    order_id: str = ""
    psp_id: str = ""
    decline_reason: str = ""
    retry_count: int = 0


@dataclass(frozen=True)
class PaymentRefundedEvent(DomainEvent):
    """
    Emitted when a captured payment is refunded.

    Triggers BARQ reconciliation adjustment and Commerce return processing.
    """

    order_id: str = ""
    psp_id: str = ""
    psp_transaction_id: str = ""
    refund_amount: float = 0.0
    currency: str = ""


@dataclass(frozen=True)
class PaymentRetriedEvent(DomainEvent):
    """
    Emitted when a declined payment is retried with a different PSP.

    Carries the cascade decision for observability and analytics.
    """

    order_id: str = ""
    previous_psp: str = ""
    next_psp: str = ""
    retry_count: int = 0
    decline_reason: str = ""


@dataclass(frozen=True)
class FXRateQuotedEvent(DomainEvent):
    """
    Emitted when an FX rate quote is obtained from a provider.

    Enables Intelligence context to track FX rate trends and provider performance.
    """

    source_currency: str = ""
    target_currency: str = ""
    rate: float = 0.0
    provider: str = ""
