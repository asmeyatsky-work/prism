"""
Tests — FX Domain Service

Verifies:
- Best rate selection from multiple providers
- FX rate comparison with savings calculation
- DCC calculation with markup
- Rate expiry detection
- Edge cases: empty rate list, negative markup, expired rates
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from prism.shared.domain.value_objects import Currency, Money

from prism.payment.domain.services.fx_service import FXService
from prism.payment.domain.value_objects.fx import FXRate


# -- Fixtures ------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(UTC)


def _rate(
    rate: float,
    provider: str = "ecb",
    source: Currency = Currency.USD,
    target: Currency = Currency.EUR,
    ttl_minutes: int = 5,
) -> FXRate:
    now = _now()
    return FXRate(
        source_currency=source,
        target_currency=target,
        rate=rate,
        provider=provider,
        quoted_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )


def _expired_rate(
    rate: float = 0.92,
    provider: str = "ecb",
) -> FXRate:
    past = _now() - timedelta(hours=1)
    return FXRate(
        source_currency=Currency.USD,
        target_currency=Currency.EUR,
        rate=rate,
        provider=provider,
        quoted_at=past - timedelta(minutes=5),
        expires_at=past,
    )


# -- Best rate selection -------------------------------------------------

class TestSelectBestRate:
    def test_selects_highest_rate(self) -> None:
        rates = [
            _rate(0.9100, provider="provider_a"),
            _rate(0.9250, provider="provider_b"),
            _rate(0.9180, provider="provider_c"),
        ]

        best = FXService.select_best_rate(rates)

        assert best.provider == "provider_b"
        assert best.rate == 0.9250

    def test_single_rate_returns_that_rate(self) -> None:
        rates = [_rate(0.92, provider="single")]
        assert FXService.select_best_rate(rates).provider == "single"

    def test_empty_rates_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            FXService.select_best_rate([])


# -- Rate comparison -----------------------------------------------------

class TestCompareRates:
    def test_comparison_calculates_savings(self) -> None:
        rates = [
            _rate(0.9100, provider="provider_a"),
            _rate(0.9250, provider="provider_b"),
        ]
        amount = Money(amount=10000.00, currency=Currency.USD)

        comparison = FXService.compare_rates(rates, amount)

        assert comparison.best_rate.provider == "provider_b"
        assert len(comparison.rates) == 2
        # Savings: 10000 * (0.925 - 0.91) = 150.0
        assert comparison.savings_vs_worst.amount == 150.0
        assert comparison.savings_vs_worst.currency == Currency.EUR

    def test_comparison_with_identical_rates_has_zero_savings(self) -> None:
        rates = [
            _rate(0.92, provider="provider_a"),
            _rate(0.92, provider="provider_b"),
        ]
        amount = Money(amount=5000.00, currency=Currency.USD)

        comparison = FXService.compare_rates(rates, amount)

        assert comparison.savings_vs_worst.amount == 0.0

    def test_comparison_empty_rates_raises(self) -> None:
        amount = Money(amount=1000.00, currency=Currency.USD)
        with pytest.raises(ValueError, match="empty"):
            FXService.compare_rates([], amount)


# -- DCC calculation -----------------------------------------------------

class TestDCCCalculation:
    def test_dcc_with_zero_markup(self) -> None:
        rate = _rate(0.92)
        amount = Money(amount=1000.00, currency=Currency.USD)

        dcc = FXService.calculate_dcc(amount, rate, markup=0.0)

        assert dcc.customer_sees.amount == 920.00
        assert dcc.customer_sees.currency == Currency.EUR
        assert dcc.merchant_receives == amount
        assert dcc.markup_percentage == 0.0

    def test_dcc_with_markup(self) -> None:
        rate = _rate(0.92)
        amount = Money(amount=1000.00, currency=Currency.USD)

        dcc = FXService.calculate_dcc(amount, rate, markup=3.0)

        # Marked-up rate: 0.92 * 1.03 = 0.9476
        # Customer sees: 1000 * 0.9476 = 947.60
        assert dcc.customer_sees.amount == 947.60
        assert dcc.markup_percentage == 3.0
        assert dcc.merchant_receives.amount == 1000.00

    def test_dcc_negative_markup_raises(self) -> None:
        rate = _rate(0.92)
        amount = Money(amount=1000.00, currency=Currency.USD)

        with pytest.raises(ValueError, match="negative"):
            FXService.calculate_dcc(amount, rate, markup=-1.0)

    def test_dcc_preserves_fx_rate(self) -> None:
        rate = _rate(0.92, provider="xe")
        amount = Money(amount=500.00, currency=Currency.USD)

        dcc = FXService.calculate_dcc(amount, rate, markup=2.5)

        assert dcc.fx_rate == rate
        assert dcc.fx_rate.provider == "xe"


# -- Rate expiry ---------------------------------------------------------

class TestRateExpiry:
    def test_valid_rate_is_not_expired(self) -> None:
        rate = _rate(0.92, ttl_minutes=5)
        assert FXService.is_rate_expired(rate) is False

    def test_expired_rate_is_detected(self) -> None:
        rate = _expired_rate()
        assert FXService.is_rate_expired(rate) is True


# -- FXRate value object tests -------------------------------------------

class TestFXRateValueObject:
    def test_convert_money(self) -> None:
        rate = _rate(0.92)
        amount = Money(amount=100.00, currency=Currency.USD)

        converted = rate.convert(amount)

        assert converted.amount == 92.00
        assert converted.currency == Currency.EUR

    def test_convert_wrong_currency_raises(self) -> None:
        rate = _rate(0.92, source=Currency.USD, target=Currency.EUR)
        amount = Money(amount=100.00, currency=Currency.GBP)

        with pytest.raises(ValueError, match="Cannot convert"):
            rate.convert(amount)

    def test_invalid_rate_raises(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            _rate(rate=-0.5)

    def test_invalid_expiry_raises(self) -> None:
        now = _now()
        with pytest.raises(ValueError, match="expires_at"):
            FXRate(
                source_currency=Currency.USD,
                target_currency=Currency.EUR,
                rate=0.92,
                provider="test",
                quoted_at=now,
                expires_at=now - timedelta(minutes=1),
            )
