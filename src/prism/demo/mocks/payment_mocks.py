"""
Payment Context — Mock PSP, FX, Routing, and BNPL Adapters

Provides mock implementations of:
- PSPPort                    -> MockPSP
- FXRatePort                 -> MockFXRate
- RoutingRuleRepositoryPort  -> MockRoutingRuleRepository
- PaymentRepositoryPort      -> InMemoryPaymentRepository
- BNPLPort                   -> MockBNPL

MockPSP simulates a 95% authorisation success rate with realistic
transaction IDs. MockFXRate returns current-ish rates for luxury-market
currency pairs. MockBNPL offers Klarna/Affirm for orders exceeding 500.
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from prism.payment.domain.entities.payment import Payment
from prism.payment.domain.entities.routing_rule import RoutingRule
from prism.payment.domain.value_objects.bnpl import (
    BNPLEligibility,
    BNPLOption,
    BNPLProvider,
)
from prism.payment.domain.value_objects.fx import FXRate
from prism.payment.domain.value_objects.routing import (
    ConditionOperator,
    RoutingCondition,
)
from prism.shared.domain.value_objects import Currency, Money

logger = logging.getLogger("prism.demo.payment")


class MockPSP:
    """
    Mock Payment Service Provider with a 95% authorisation success rate.
    Generates realistic Stripe-style transaction IDs and maintains an
    in-memory ledger of authorised/captured/refunded transactions.
    """

    _SUCCESS_RATE = 0.95

    _DECLINE_REASONS = [
        "Insufficient funds",
        "Card expired",
        "Do not honour",
        "Suspected fraud",
        "Transaction limit exceeded",
    ]

    def __init__(self, psp_name: str = "stripe_eu") -> None:
        self._psp_name = psp_name
        self._transactions: dict[str, dict[str, Any]] = {}

    async def authorise(
        self,
        amount: Money,
        currency: Currency,
        card_token: str,
    ) -> dict[str, Any]:
        transaction_id = f"txn_{self._psp_name}_{uuid.uuid4().hex[:12]}"

        if random.random() < self._SUCCESS_RATE:
            self._transactions[transaction_id] = {
                "status": "authorised",
                "amount": amount.amount,
                "currency": currency.value,
                "card_token": card_token,
                "authorised_at": datetime.now(UTC).isoformat(),
            }
            logger.info(
                "Payment authorised: %s (%.2f %s)",
                transaction_id,
                amount.amount,
                currency.value,
            )
            return {
                "transaction_id": transaction_id,
                "status": "authorised",
                "psp": self._psp_name,
                "authorised_amount": amount.amount,
                "currency": currency.value,
            }
        else:
            reason = random.choice(self._DECLINE_REASONS)
            logger.info(
                "Payment declined: %s - %s",
                transaction_id,
                reason,
            )
            return {
                "transaction_id": transaction_id,
                "status": "declined",
                "decline_reason": reason,
                "psp": self._psp_name,
            }

    async def capture(self, transaction_id: str) -> dict[str, Any]:
        txn = self._transactions.get(transaction_id)
        if not txn or txn.get("status") != "authorised":
            return {
                "status": "failed",
                "error": "Transaction not found or not in authorised state",
            }

        capture_id = f"cap_{uuid.uuid4().hex[:10]}"
        txn["status"] = "captured"
        txn["capture_id"] = capture_id
        txn["captured_at"] = datetime.now(UTC).isoformat()

        logger.info("Payment captured: %s -> %s", transaction_id, capture_id)
        return {
            "status": "captured",
            "capture_id": capture_id,
            "transaction_id": transaction_id,
        }

    async def refund(
        self,
        transaction_id: str,
        amount: Money,
    ) -> dict[str, Any]:
        txn = self._transactions.get(transaction_id)
        if not txn or txn.get("status") != "captured":
            return {
                "status": "failed",
                "error": "Transaction not found or not captured",
            }

        refund_id = f"ref_{uuid.uuid4().hex[:10]}"
        txn["status"] = "refunded"
        txn["refund_id"] = refund_id
        txn["refunded_at"] = datetime.now(UTC).isoformat()

        logger.info(
            "Payment refunded: %s -> %s (%.2f %s)",
            transaction_id,
            refund_id,
            amount.amount,
            amount.currency.value,
        )
        return {
            "status": "refunded",
            "refund_id": refund_id,
            "transaction_id": transaction_id,
            "refunded_amount": amount.amount,
        }


# ── Realistic FX rates for luxury retail currency pairs ─────────────────

_BASE_FX_RATES: dict[tuple[str, str], float] = {
    # EUR base
    ("EUR", "USD"): 1.0850,
    ("EUR", "GBP"): 0.8590,
    ("EUR", "CHF"): 0.9410,
    ("EUR", "JPY"): 162.50,
    ("EUR", "CNY"): 7.8900,
    ("EUR", "AED"): 3.9850,
    ("EUR", "HKD"): 8.4700,
    ("EUR", "SGD"): 1.4580,
    ("EUR", "KRW"): 1425.00,
    # USD base
    ("USD", "EUR"): 0.9217,
    ("USD", "GBP"): 0.7920,
    ("USD", "CHF"): 0.8670,
    ("USD", "JPY"): 149.80,
    ("USD", "CNY"): 7.2700,
    ("USD", "AED"): 3.6730,
    ("USD", "HKD"): 7.8050,
    ("USD", "SGD"): 1.3430,
    ("USD", "KRW"): 1315.00,
    # GBP base
    ("GBP", "USD"): 1.2630,
    ("GBP", "EUR"): 1.1640,
    ("GBP", "CHF"): 1.0950,
    ("GBP", "JPY"): 189.10,
    ("GBP", "CNY"): 9.1800,
    # CHF base
    ("CHF", "USD"): 1.0630,
    ("CHF", "EUR"): 1.0630,
    ("CHF", "GBP"): 0.9130,
    ("CHF", "JPY"): 172.80,
    # JPY base
    ("JPY", "USD"): 0.00668,
    ("JPY", "EUR"): 0.00615,
    ("JPY", "GBP"): 0.00529,
    # CNY base
    ("CNY", "USD"): 0.1376,
    ("CNY", "EUR"): 0.1267,
}


class MockFXRate:
    """
    Mock FX rate provider returning realistic rates for luxury-market
    currency pairs. Rates are based on static base values with a small
    random spread to simulate live market fluctuation.
    """

    async def get_rate(
        self,
        source: Currency,
        target: Currency,
    ) -> FXRate:
        if source == target:
            rate_value = 1.0
        else:
            key = (source.value, target.value)
            base_rate = _BASE_FX_RATES.get(key)
            if base_rate is None:
                # Try inverse
                inverse_key = (target.value, source.value)
                inverse_rate = _BASE_FX_RATES.get(inverse_key)
                if inverse_rate:
                    base_rate = 1.0 / inverse_rate
                else:
                    # Fallback: go through EUR
                    to_eur = _BASE_FX_RATES.get((source.value, "EUR"), 1.0)
                    from_eur = _BASE_FX_RATES.get(("EUR", target.value), 1.0)
                    base_rate = to_eur * from_eur

            # Apply small spread (+/- 0.2%)
            spread = random.uniform(-0.002, 0.002)
            rate_value = round(base_rate * (1.0 + spread), 6)

        now = datetime.now(UTC)
        return FXRate(
            source_currency=source,
            target_currency=target,
            rate=rate_value,
            provider="prism_demo_fx",
            quoted_at=now,
            expires_at=now + timedelta(minutes=15),
        )


# ── Default routing rules ──────────────────────────────────────────────

_DEFAULT_ROUTING_RULES: dict[str, list[RoutingRule]] = {
    "gucci": [
        RoutingRule(
            tenant_id="gucci",
            name="EU Stripe Primary",
            conditions=(
                RoutingCondition(
                    field="currency",
                    operator=ConditionOperator.IN,
                    value=("EUR", "GBP", "CHF"),
                ),
            ),
            target_psp="stripe_eu",
            priority=1,
            enabled=True,
        ),
        RoutingRule(
            tenant_id="gucci",
            name="APAC Planet Primary",
            conditions=(
                RoutingCondition(
                    field="currency",
                    operator=ConditionOperator.IN,
                    value=("JPY", "CNY", "HKD", "SGD", "KRW"),
                ),
            ),
            target_psp="planet_apac",
            priority=2,
            enabled=True,
        ),
        RoutingRule(
            tenant_id="gucci",
            name="Global Adyen Fallback",
            conditions=(),
            target_psp="adyen_global",
            priority=99,
            enabled=True,
        ),
    ],
    "lvmh": [
        RoutingRule(
            tenant_id="lvmh",
            name="LVMH Stripe Primary",
            conditions=(
                RoutingCondition(
                    field="currency",
                    operator=ConditionOperator.IN,
                    value=("EUR", "USD", "GBP"),
                ),
            ),
            target_psp="stripe_eu",
            priority=1,
            enabled=True,
        ),
        RoutingRule(
            tenant_id="lvmh",
            name="LVMH Global Fallback",
            conditions=(),
            target_psp="adyen_global",
            priority=99,
            enabled=True,
        ),
    ],
}


class MockRoutingRuleRepository:
    """
    In-memory routing rule repository pre-seeded with default rules
    for "gucci" and "lvmh" tenants. Supports adding custom rules.
    """

    def __init__(self) -> None:
        self._rules: dict[str, list[RoutingRule]] = {
            k: list(v) for k, v in _DEFAULT_ROUTING_RULES.items()
        }

    async def get_rules(self, tenant_id: str) -> list[RoutingRule]:
        rules = self._rules.get(tenant_id, [])
        return sorted(rules, key=lambda r: r.priority)

    async def save_rule(self, rule: RoutingRule) -> None:
        if rule.tenant_id not in self._rules:
            self._rules[rule.tenant_id] = []
        # Replace existing rule with same name or append
        self._rules[rule.tenant_id] = [
            r for r in self._rules[rule.tenant_id] if r.name != rule.name
        ]
        self._rules[rule.tenant_id].append(rule)


class InMemoryPaymentRepository:
    """
    In-memory payment aggregate repository keyed by payment ID and order ID.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, Payment] = {}
        self._by_order: dict[str, Payment] = {}

    async def save(self, payment: Payment) -> None:
        self._by_id[payment.id] = payment
        if payment.order_id:
            self._by_order[payment.order_id] = payment

    async def get_by_id(self, payment_id: str) -> Payment | None:
        return self._by_id.get(payment_id)

    async def get_by_order_id(self, order_id: str) -> Payment | None:
        return self._by_order.get(order_id)


class MockBNPL:
    """
    Mock BNPL eligibility checker. Returns Klarna and Affirm installment
    options for purchase amounts exceeding 500 in the order currency.
    Below 500, returns ineligible.
    """

    _MINIMUM_AMOUNT = 500.0

    async def check_eligibility(
        self,
        amount: Money,
        customer_id: str,
    ) -> BNPLEligibility:
        if amount.amount < self._MINIMUM_AMOUNT:
            return BNPLEligibility(eligible=False)

        currency = amount.currency
        options: list[BNPLOption] = []

        # Klarna: 4 interest-free installments (up to 10,000)
        options.append(
            BNPLOption(
                provider=BNPLProvider.KLARNA,
                min_amount=Money(amount=200.0, currency=currency),
                max_amount=Money(amount=10000.0, currency=currency),
                installments=4,
                interest_rate=0.0,
            )
        )

        # Affirm: 6 installments at 4.9% APR (for amounts > 1000)
        if amount.amount >= 1000.0:
            options.append(
                BNPLOption(
                    provider=BNPLProvider.AFFIRM,
                    min_amount=Money(amount=500.0, currency=currency),
                    max_amount=Money(amount=25000.0, currency=currency),
                    installments=6,
                    interest_rate=4.9,
                )
            )

        # Affirm: 12 installments at 9.9% APR (for luxury purchases > 2500)
        if amount.amount >= 2500.0:
            options.append(
                BNPLOption(
                    provider=BNPLProvider.AFFIRM,
                    min_amount=Money(amount=2000.0, currency=currency),
                    max_amount=Money(amount=50000.0, currency=currency),
                    installments=12,
                    interest_rate=9.9,
                )
            )

        # Filter options to only those that cover the actual amount
        valid_options = tuple(opt for opt in options if opt.covers_amount(amount))

        if not valid_options:
            return BNPLEligibility(eligible=False)

        return BNPLEligibility(eligible=True, options=valid_options)
