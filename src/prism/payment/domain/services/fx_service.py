"""
Payment Domain — FX Domain Service

Architectural Intent:
- Pure domain service for FX rate selection and DCC calculation
- No infrastructure dependencies — operates on value objects only
- select_best_rate picks the highest rate (most favourable for conversion)
- calculate_dcc builds the DCC offer with disclosed markup
- is_rate_expired guards against stale FX quotes before authorisation
"""

from __future__ import annotations

from datetime import UTC, datetime

from prism.shared.domain.value_objects import Money

from prism.payment.domain.value_objects.fx import (
    DynamicCurrencyConversion,
    FXComparison,
    FXRate,
)


class FXService:
    """
    FX domain service — rate selection, DCC calculation, and expiry checks.

    Pure domain logic: no I/O, no async, no infrastructure coupling.
    """

    @staticmethod
    def select_best_rate(rates: list[FXRate]) -> FXRate:
        """
        Select the most favourable FX rate from a list of provider quotes.

        "Best" means the highest conversion rate, giving the customer more
        units of the target currency per unit of source currency.
        """
        if not rates:
            raise ValueError("Cannot select best rate from an empty list")
        return max(rates, key=lambda r: r.rate)

    @staticmethod
    def compare_rates(rates: list[FXRate], amount: Money) -> FXComparison:
        """
        Build an FXComparison from multiple provider quotes.

        Calculates the savings between the best and worst rates for the
        given amount, providing transparency for the routing decision.
        """
        if not rates:
            raise ValueError("Cannot compare empty rate list")

        best = max(rates, key=lambda r: r.rate)
        worst = min(rates, key=lambda r: r.rate)

        best_converted = round(amount.amount * best.rate, 2)
        worst_converted = round(amount.amount * worst.rate, 2)
        savings_amount = round(best_converted - worst_converted, 2)

        return FXComparison(
            rates=tuple(rates),
            best_rate=best,
            savings_vs_worst=Money(
                amount=savings_amount,
                currency=best.target_currency,
            ),
        )

    @staticmethod
    def calculate_dcc(
        amount: Money,
        rate: FXRate,
        markup: float,
    ) -> DynamicCurrencyConversion:
        """
        Calculate a Dynamic Currency Conversion offer.

        The customer sees the price in their home currency (with markup applied),
        while the merchant receives the original amount in settlement currency.
        The markup percentage is disclosed per PSD2 / IFR requirements.
        """
        if markup < 0:
            raise ValueError("Markup cannot be negative")

        marked_up_rate = rate.rate * (1 + markup / 100)
        customer_amount = round(amount.amount * marked_up_rate, 2)

        return DynamicCurrencyConversion(
            customer_sees=Money(
                amount=customer_amount,
                currency=rate.target_currency,
            ),
            merchant_receives=amount,
            fx_rate=rate,
            markup_percentage=markup,
        )

    @staticmethod
    def is_rate_expired(rate: FXRate) -> bool:
        """
        Check whether an FX rate quote has expired.

        Expired rates must not be used for authorisation; a fresh quote
        should be obtained from the provider.
        """
        return datetime.now(UTC) >= rate.expires_at
