"""
Tests — FlowRoute Routing Service

Verifies:
- Rule-based routing (first matching rule wins, ordered by priority)
- Capability-based fallback scoring when no rules match
- Cascade retry eligibility (retryable vs non-retryable decline reasons)
- Cascade PSP selection (round-robin through alternatives)
- Edge cases: no rules, no capabilities, disabled rules
"""

from __future__ import annotations

import pytest

from prism.shared.domain.value_objects import Currency, Money

from prism.payment.domain.entities.payment import Payment
from prism.payment.domain.entities.routing_rule import RoutingRule
from prism.payment.domain.services.routing_service import RoutingService
from prism.payment.domain.value_objects.routing import (
    ConditionOperator,
    PSPCapability,
    RoutingCondition,
)


# -- Fixtures ------------------------------------------------------------

def _make_payment(**overrides) -> Payment:
    defaults = dict(
        order_id="order-001",
        tenant_id="tenant-luxury",
        amount=Money(amount=2000.00, currency=Currency.EUR),
        customer_currency=Currency.USD,
        settlement_currency=Currency.EUR,
    )
    defaults.update(overrides)
    return Payment.create(**defaults)


def _eur_rule(priority: int = 1, psp: str = "stripe") -> RoutingRule:
    return RoutingRule(
        tenant_id="tenant-luxury",
        name=f"EUR-to-{psp}",
        conditions=(
            RoutingCondition(
                field="currency",
                operator=ConditionOperator.EQ,
                value="EUR",
            ),
        ),
        target_psp=psp,
        priority=priority,
        enabled=True,
    )


def _high_value_rule(threshold: float = 5000.0, psp: str = "planet_payment") -> RoutingRule:
    return RoutingRule(
        tenant_id="tenant-luxury",
        name=f"high-value-to-{psp}",
        conditions=(
            RoutingCondition(
                field="amount",
                operator=ConditionOperator.GT,
                value=threshold,
            ),
        ),
        target_psp=psp,
        priority=0,
        enabled=True,
    )


def _stripe_capability() -> PSPCapability:
    return PSPCapability(
        psp_id="stripe",
        supported_currencies=(Currency.EUR, Currency.USD, Currency.GBP),
        supported_card_types=("visa", "mastercard", "amex"),
        avg_auth_rate=0.95,
    )


def _planet_capability() -> PSPCapability:
    return PSPCapability(
        psp_id="planet_payment",
        supported_currencies=(Currency.EUR, Currency.AED, Currency.SAR, Currency.USD),
        supported_card_types=("visa", "mastercard"),
        avg_auth_rate=0.88,
    )


# -- Rule-based routing --------------------------------------------------

class TestRuleBasedRouting:
    def test_single_matching_rule_selects_psp(self) -> None:
        payment = _make_payment()
        rules = [_eur_rule(priority=1, psp="stripe")]
        capabilities = [_stripe_capability(), _planet_capability()]

        decision = RoutingService.evaluate_route(payment, rules, capabilities)

        assert decision.selected_psp == "stripe"
        assert "EUR-to-stripe" in decision.reason

    def test_highest_priority_rule_wins(self) -> None:
        payment = _make_payment()
        rules = [
            _eur_rule(priority=10, psp="stripe"),
            _eur_rule(priority=1, psp="planet_payment"),
        ]
        capabilities = [_stripe_capability(), _planet_capability()]

        decision = RoutingService.evaluate_route(payment, rules, capabilities)

        assert decision.selected_psp == "planet_payment"
        assert "priority 1" in decision.reason

    def test_disabled_rule_is_skipped(self) -> None:
        payment = _make_payment()
        disabled = RoutingRule(
            tenant_id="tenant-luxury",
            name="disabled-rule",
            conditions=(
                RoutingCondition(field="currency", operator=ConditionOperator.EQ, value="EUR"),
            ),
            target_psp="disabled_psp",
            priority=0,
            enabled=False,
        )
        rules = [disabled, _eur_rule(priority=5, psp="stripe")]
        capabilities = [_stripe_capability()]

        decision = RoutingService.evaluate_route(payment, rules, capabilities)

        assert decision.selected_psp == "stripe"

    def test_non_matching_rule_is_skipped(self) -> None:
        payment = _make_payment()  # EUR, amount=2000
        rules = [_high_value_rule(threshold=5000.0, psp="planet_payment")]
        capabilities = [_stripe_capability(), _planet_capability()]

        # No rule matches -> falls back to capability scoring
        decision = RoutingService.evaluate_route(payment, rules, capabilities)

        assert "scoring" in decision.reason.lower()

    def test_alternatives_populated_on_rule_match(self) -> None:
        payment = _make_payment()
        rules = [_eur_rule(priority=1, psp="stripe")]
        capabilities = [_stripe_capability(), _planet_capability()]

        decision = RoutingService.evaluate_route(payment, rules, capabilities)

        assert "planet_payment" in decision.alternatives


# -- Capability-based fallback -------------------------------------------

class TestCapabilityBasedRouting:
    def test_no_rules_uses_capability_scoring(self) -> None:
        payment = _make_payment()
        capabilities = [_stripe_capability(), _planet_capability()]

        decision = RoutingService.evaluate_route(payment, [], capabilities)

        # Stripe has higher auth rate (0.95 vs 0.88) and supports EUR
        assert decision.selected_psp == "stripe"
        assert "scoring" in decision.reason.lower()

    def test_no_capabilities_raises(self) -> None:
        payment = _make_payment()

        with pytest.raises(ValueError, match="No PSP capabilities"):
            RoutingService.evaluate_route(payment, [], [])

    def test_currency_mismatch_penalises_psp(self) -> None:
        """A PSP that doesn't support the payment currency gets a lower score."""
        payment = _make_payment(amount=Money(amount=1000.0, currency=Currency.KRW))

        krw_psp = PSPCapability(
            psp_id="krw_specialist",
            supported_currencies=(Currency.KRW,),
            supported_card_types=("visa",),
            avg_auth_rate=0.80,
        )
        generic_psp = PSPCapability(
            psp_id="generic",
            supported_currencies=(Currency.EUR, Currency.USD),
            supported_card_types=("visa", "mastercard"),
            avg_auth_rate=0.95,
        )

        decision = RoutingService.evaluate_route(payment, [], [krw_psp, generic_psp])

        # krw_specialist: 0.80 * 1.2 = 0.96
        # generic: 0.95 * 0.3 = 0.285
        assert decision.selected_psp == "krw_specialist"


# -- Cascade retry -------------------------------------------------------

class TestCascadeRetry:
    @pytest.mark.parametrize(
        "reason,expected",
        [
            ("insufficient_funds", True),
            ("processor_declined", True),
            ("do_not_honor", True),
            ("network_error", True),
            ("timeout", True),
            ("lost_or_stolen_card", False),
            ("expired_card", False),
            ("fraud_suspected", False),
            ("", False),
            (None, False),
        ],
    )
    def test_should_cascade(self, reason: str | None, expected: bool) -> None:
        assert RoutingService.should_cascade(reason, retry_count=0) == expected

    def test_should_not_cascade_when_retries_exhausted(self) -> None:
        assert RoutingService.should_cascade("insufficient_funds", retry_count=3) is False

    def test_select_cascade_psp_picks_first_alternative(self) -> None:
        next_psp = RoutingService.select_cascade_psp(
            current_psp="stripe",
            alternatives=("planet_payment", "adyen"),
            decline_pattern="insufficient_funds",
        )
        assert next_psp == "planet_payment"

    def test_select_cascade_psp_skips_current(self) -> None:
        next_psp = RoutingService.select_cascade_psp(
            current_psp="stripe",
            alternatives=("stripe", "planet_payment"),
            decline_pattern="insufficient_funds",
        )
        assert next_psp == "planet_payment"

    def test_select_cascade_psp_no_alternatives_raises(self) -> None:
        with pytest.raises(ValueError, match="No alternative PSPs"):
            RoutingService.select_cascade_psp(
                current_psp="stripe",
                alternatives=("stripe",),
                decline_pattern="insufficient_funds",
            )
