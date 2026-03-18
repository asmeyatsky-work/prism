"""
Payment Domain — FX Value Objects

Architectural Intent:
- Immutable value objects for foreign-exchange rate handling
- FXRate captures a single provider quote with expiry semantics
- FXComparison aggregates competing quotes for parallelism-first rate shopping
- DynamicCurrencyConversion encapsulates the DCC offer shown to the customer

These objects are pure domain; they carry no infrastructure dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from prism.shared.domain.value_objects import Currency, Money, ValueObject


@dataclass(frozen=True)
class FXRate(ValueObject):
    """
    A single FX rate quote from a provider.

    Immutable snapshot of a rate at a point in time. The domain layer uses
    ``expires_at`` to determine staleness — expired quotes must be refreshed
    before authorisation.
    """

    source_currency: Currency
    target_currency: Currency
    rate: float
    provider: str
    quoted_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.rate <= 0:
            raise ValueError("FX rate must be positive")
        if self.expires_at <= self.quoted_at:
            raise ValueError("expires_at must be after quoted_at")

    def convert(self, amount: Money) -> Money:
        """Convert a Money amount using this rate."""
        if amount.currency != self.source_currency:
            raise ValueError(
                f"Cannot convert {amount.currency} with a "
                f"{self.source_currency}->{self.target_currency} rate"
            )
        return Money(
            amount=round(amount.amount * self.rate, 2),
            currency=self.target_currency,
        )


@dataclass(frozen=True)
class FXComparison(ValueObject):
    """
    Result of parallel FX rate shopping across multiple providers.

    ``rates`` is a tuple so this remains hashable and immutable.
    ``best_rate`` is the provider offering the most favourable conversion.
    ``savings_vs_worst`` shows the monetary delta, motivating provider choice.
    """

    rates: tuple[FXRate, ...]
    best_rate: FXRate
    savings_vs_worst: Money

    def __post_init__(self) -> None:
        if not self.rates:
            raise ValueError("FXComparison requires at least one rate")
        if self.best_rate not in self.rates:
            raise ValueError("best_rate must be one of the provided rates")


@dataclass(frozen=True)
class DynamicCurrencyConversion(ValueObject):
    """
    DCC offer presented to the customer at checkout.

    The customer sees the price in their home currency; the merchant settles
    in their preferred currency. The markup percentage is disclosed per
    regulatory requirements.
    """

    customer_sees: Money
    merchant_receives: Money
    fx_rate: FXRate
    markup_percentage: float

    def __post_init__(self) -> None:
        if self.markup_percentage < 0:
            raise ValueError("Markup percentage cannot be negative")
