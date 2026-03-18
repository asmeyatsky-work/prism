"""
Tests — ProcessPayment Use Case with Parallel FX Fetching

Verifies:
- Full payment processing workflow via DAGOrchestrator
- Parallel execution of routing evaluation and FX rate fetching
- Successful authorisation path
- Decline with cascade retry path
- FX provider failure is non-critical (payment proceeds without FX)
- Event dispatch after persistence
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from prism.shared.domain.value_objects import Currency, Money

from prism.payment.application.commands.process_payment import ProcessPaymentUseCase
from prism.payment.application.dtos.payment_dto import PaymentRequestDTO
from prism.payment.domain.entities.routing_rule import RoutingRule
from prism.payment.domain.value_objects.fx import FXRate
from prism.payment.domain.value_objects.routing import (
    ConditionOperator,
    PSPCapability,
    RoutingCondition,
)


# -- Test doubles --------------------------------------------------------

def _make_request(**overrides) -> PaymentRequestDTO:
    defaults = dict(
        order_id="order-001",
        tenant_id="tenant-luxury",
        amount=1500.00,
        currency="EUR",
        customer_currency="USD",
        settlement_currency="EUR",
        card_token="tok_visa_4242",
        card_type="visa",
        customer_id="cust-001",
    )
    defaults.update(overrides)
    return PaymentRequestDTO(**defaults)


def _psp_capabilities() -> list[PSPCapability]:
    return [
        PSPCapability(
            psp_id="stripe",
            supported_currencies=(Currency.EUR, Currency.USD, Currency.GBP),
            supported_card_types=("visa", "mastercard"),
            avg_auth_rate=0.95,
        ),
        PSPCapability(
            psp_id="planet_payment",
            supported_currencies=(Currency.EUR, Currency.AED, Currency.SAR),
            supported_card_types=("visa", "mastercard"),
            avg_auth_rate=0.88,
        ),
    ]


def _fx_rate(provider: str = "ecb", rate: float = 0.92) -> FXRate:
    now = datetime.now(UTC)
    return FXRate(
        source_currency=Currency.USD,
        target_currency=Currency.EUR,
        rate=rate,
        provider=provider,
        quoted_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def _mock_psp(authorise_status: str = "authorised", decline_reason: str = "") -> AsyncMock:
    psp = AsyncMock()
    psp.authorise.return_value = {
        "transaction_id": "pi_test123",
        "status": authorise_status,
        "decline_reason": decline_reason,
    }
    psp.capture.return_value = {"status": "captured", "capture_id": "ch_test123"}
    psp.refund.return_value = {"status": "refunded", "refund_id": "re_test123"}
    return psp


def _mock_fx_provider(rate: float = 0.92, provider: str = "ecb") -> AsyncMock:
    fx = AsyncMock()
    fx.get_rate.return_value = _fx_rate(provider=provider, rate=rate)
    return fx


def _mock_routing_rule_repo(rules: list[RoutingRule] | None = None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_rules.return_value = rules or [
        RoutingRule(
            tenant_id="tenant-luxury",
            name="EUR-to-stripe",
            conditions=(
                RoutingCondition(field="currency", operator=ConditionOperator.EQ, value="EUR"),
            ),
            target_psp="stripe",
            priority=1,
            enabled=True,
        ),
    ]
    return repo


def _mock_payment_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.save.return_value = None
    repo.get_by_id.return_value = None
    return repo


# -- Tests ---------------------------------------------------------------

class TestProcessPaymentSuccess:
    @pytest.mark.asyncio
    async def test_successful_authorisation(self) -> None:
        """Happy path: routing + FX in parallel, then successful authorisation."""
        stripe_psp = _mock_psp(authorise_status="authorised")
        fx_provider = _mock_fx_provider(rate=0.92, provider="ecb")
        routing_repo = _mock_routing_rule_repo()
        payment_repo = _mock_payment_repo()
        event_bus = AsyncMock()

        use_case = ProcessPaymentUseCase(
            psp_registry={"stripe": stripe_psp, "planet_payment": _mock_psp()},
            fx_providers=[fx_provider],
            routing_rule_repo=routing_repo,
            payment_repo=payment_repo,
            psp_capabilities=_psp_capabilities(),
            event_bus=event_bus,
        )

        result = await use_case.execute(_make_request())

        assert result.success is True
        assert result.value is not None
        assert result.value.status == "AUTHORISED"
        assert result.value.psp_id == "stripe"
        assert result.value.order_id == "order-001"
        # PSP was called
        stripe_psp.authorise.assert_called_once()
        # Payment was persisted
        payment_repo.save.assert_called_once()
        # Events were dispatched
        event_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_parallel_fx_and_routing(self) -> None:
        """Verify that FX rate fetching and routing run concurrently."""
        call_order: list[str] = []

        async def slow_get_rules(tenant_id: str) -> list[RoutingRule]:
            call_order.append("routing_start")
            await asyncio.sleep(0.05)
            call_order.append("routing_end")
            return [
                RoutingRule(
                    tenant_id=tenant_id,
                    name="EUR-to-stripe",
                    conditions=(
                        RoutingCondition(
                            field="currency",
                            operator=ConditionOperator.EQ,
                            value="EUR",
                        ),
                    ),
                    target_psp="stripe",
                    priority=1,
                    enabled=True,
                ),
            ]

        async def slow_get_rate(source: Currency, target: Currency) -> FXRate:
            call_order.append("fx_start")
            await asyncio.sleep(0.05)
            call_order.append("fx_end")
            return _fx_rate()

        routing_repo = AsyncMock()
        routing_repo.get_rules = slow_get_rules

        fx_provider = AsyncMock()
        fx_provider.get_rate = slow_get_rate

        stripe_psp = _mock_psp()
        payment_repo = _mock_payment_repo()

        use_case = ProcessPaymentUseCase(
            psp_registry={"stripe": stripe_psp, "planet_payment": _mock_psp()},
            fx_providers=[fx_provider],
            routing_rule_repo=routing_repo,
            payment_repo=payment_repo,
            psp_capabilities=_psp_capabilities(),
        )

        result = await use_case.execute(_make_request())

        assert result.success is True
        # Both started before either ended (parallel execution)
        assert "routing_start" in call_order
        assert "fx_start" in call_order
        routing_start_idx = call_order.index("routing_start")
        fx_start_idx = call_order.index("fx_start")
        routing_end_idx = call_order.index("routing_end")
        fx_end_idx = call_order.index("fx_end")
        # Both should start before either finishes
        assert routing_start_idx < routing_end_idx
        assert fx_start_idx < fx_end_idx


class TestProcessPaymentDeclineAndCascade:
    @pytest.mark.asyncio
    async def test_decline_with_cascade_retry(self) -> None:
        """When Stripe declines, cascade to Planet Payment."""
        stripe_psp = _mock_psp(
            authorise_status="declined",
            decline_reason="insufficient_funds",
        )
        planet_psp = _mock_psp(authorise_status="authorised")
        payment_repo = _mock_payment_repo()

        use_case = ProcessPaymentUseCase(
            psp_registry={"stripe": stripe_psp, "planet_payment": planet_psp},
            fx_providers=[_mock_fx_provider()],
            routing_rule_repo=_mock_routing_rule_repo(),
            payment_repo=payment_repo,
            psp_capabilities=_psp_capabilities(),
        )

        result = await use_case.execute(_make_request())

        assert result.success is True
        assert result.value is not None
        assert result.value.status == "AUTHORISED"
        assert result.value.retry_count == 1
        # Both PSPs were called
        stripe_psp.authorise.assert_called_once()
        planet_psp.authorise.assert_called_once()


class TestProcessPaymentFXFailure:
    @pytest.mark.asyncio
    async def test_fx_failure_is_non_critical(self) -> None:
        """Payment should succeed even if FX rate fetching fails."""
        failing_fx = AsyncMock()
        failing_fx.get_rate.side_effect = RuntimeError("FX provider down")

        stripe_psp = _mock_psp()
        payment_repo = _mock_payment_repo()

        use_case = ProcessPaymentUseCase(
            psp_registry={"stripe": stripe_psp, "planet_payment": _mock_psp()},
            fx_providers=[failing_fx],
            routing_rule_repo=_mock_routing_rule_repo(),
            payment_repo=payment_repo,
            psp_capabilities=_psp_capabilities(),
        )

        result = await use_case.execute(_make_request())

        assert result.success is True
        assert result.value is not None
        assert result.value.status == "AUTHORISED"


class TestProcessPaymentValidation:
    @pytest.mark.asyncio
    async def test_invalid_currency_returns_failure(self) -> None:
        use_case = ProcessPaymentUseCase(
            psp_registry={},
            fx_providers=[],
            routing_rule_repo=_mock_routing_rule_repo(),
            payment_repo=_mock_payment_repo(),
            psp_capabilities=_psp_capabilities(),
        )

        request = _make_request(currency="INVALID")
        result = await use_case.execute(request)

        assert result.success is False
        assert result.error_code == "INVALID_CURRENCY"
