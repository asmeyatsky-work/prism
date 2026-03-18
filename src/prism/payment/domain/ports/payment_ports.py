"""
Payment Domain — Ports (Protocol-Based Interfaces)

Architectural Intent:
- Protocol-based ports define the contracts that infrastructure adapters implement
- No concrete classes or implementations in this module
- PSPPort: gateway to payment service providers (Stripe, Planet, etc.)
- FXRatePort: gateway to FX rate providers
- RoutingRuleRepositoryPort: persistence for routing rules
- PaymentRepositoryPort: persistence for Payment aggregates
- BNPLPort: gateway to BNPL providers (Klarna, Affirm, etc.)

Per skill2026 Rule 4: Ports live in the domain layer; adapters in infrastructure.
"""

from __future__ import annotations

from typing import Any, Protocol

from prism.shared.domain.value_objects import Currency, Money

from prism.payment.domain.entities.payment import Payment
from prism.payment.domain.entities.routing_rule import RoutingRule
from prism.payment.domain.value_objects.bnpl import BNPLEligibility
from prism.payment.domain.value_objects.fx import FXRate


class PSPPort(Protocol):
    """
    Port for interacting with a Payment Service Provider.

    Each PSP adapter (Stripe, Planet Payment, etc.) implements this protocol.
    All methods are async to support non-blocking I/O.
    """

    async def authorise(
        self,
        amount: Money,
        currency: Currency,
        card_token: str,
    ) -> dict[str, Any]:
        """
        Request payment authorisation from the PSP.

        Returns a dict with at minimum:
        - ``transaction_id``: the PSP's reference for this authorisation
        - ``status``: "authorised" or "declined"
        - ``decline_reason``: present only when status is "declined"
        """
        ...

    async def capture(self, transaction_id: str) -> dict[str, Any]:
        """
        Capture a previously authorised payment.

        Returns a dict with:
        - ``status``: "captured" or "failed"
        - ``capture_id``: the PSP's capture reference
        """
        ...

    async def refund(
        self,
        transaction_id: str,
        amount: Money,
    ) -> dict[str, Any]:
        """
        Refund a captured payment (full or partial).

        Returns a dict with:
        - ``status``: "refunded" or "failed"
        - ``refund_id``: the PSP's refund reference
        """
        ...


class FXRatePort(Protocol):
    """
    Port for fetching FX rates from an external provider.

    Multiple adapters may implement this for rate shopping (parallelism-first).
    """

    async def get_rate(
        self,
        source: Currency,
        target: Currency,
    ) -> FXRate:
        """Fetch the current FX rate for a currency pair."""
        ...


class RoutingRuleRepositoryPort(Protocol):
    """Port for persisting and retrieving tenant-scoped routing rules."""

    async def get_rules(self, tenant_id: str) -> list[RoutingRule]:
        """Retrieve all routing rules for a tenant, in priority order."""
        ...

    async def save_rule(self, rule: RoutingRule) -> None:
        """Persist a routing rule."""
        ...


class PaymentRepositoryPort(Protocol):
    """Port for persisting and retrieving Payment aggregates."""

    async def save(self, payment: Payment) -> None:
        """Persist a Payment aggregate (insert or update)."""
        ...

    async def get_by_id(self, payment_id: str) -> Payment | None:
        """Retrieve a Payment by its aggregate ID."""
        ...

    async def get_by_order_id(self, order_id: str) -> Payment | None:
        """Retrieve a Payment by its associated order ID."""
        ...


class BNPLPort(Protocol):
    """
    Port for checking Buy Now Pay Later eligibility.

    Adapters connect to BNPL providers (Klarna, Affirm, etc.) to
    determine available installment plans for a customer and amount.
    """

    async def check_eligibility(
        self,
        amount: Money,
        customer_id: str,
    ) -> BNPLEligibility:
        """Check BNPL eligibility for a customer and purchase amount."""
        ...
