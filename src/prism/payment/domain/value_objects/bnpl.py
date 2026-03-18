"""
Payment Domain — BNPL Value Objects

Architectural Intent:
- Immutable value objects for Buy Now Pay Later eligibility and options
- BNPLOption describes a single installment plan from a provider
- BNPLEligibility aggregates the full eligibility result for a customer
- Provider enum is extensible as new BNPL providers are onboarded
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from prism.shared.domain.value_objects import Money, ValueObject


class BNPLProvider(str, Enum):
    """Supported Buy Now Pay Later providers."""

    KLARNA = "KLARNA"
    AFFIRM = "AFFIRM"
    OTHER = "OTHER"


@dataclass(frozen=True)
class BNPLOption(ValueObject):
    """
    A single BNPL installment plan offered by a provider.

    Describes the terms: number of installments, interest rate, and
    the permitted amount range for the plan.
    """

    provider: BNPLProvider
    min_amount: Money
    max_amount: Money
    installments: int
    interest_rate: float

    def __post_init__(self) -> None:
        if self.installments < 1:
            raise ValueError("installments must be at least 1")
        if self.interest_rate < 0:
            raise ValueError("interest_rate cannot be negative")
        if self.min_amount.amount > self.max_amount.amount:
            raise ValueError("min_amount cannot exceed max_amount")
        if self.min_amount.currency != self.max_amount.currency:
            raise ValueError("min_amount and max_amount must share the same currency")

    def covers_amount(self, amount: Money) -> bool:
        """Check if the given amount falls within this plan's range."""
        if amount.currency != self.min_amount.currency:
            return False
        return self.min_amount.amount <= amount.amount <= self.max_amount.amount


@dataclass(frozen=True)
class BNPLEligibility(ValueObject):
    """
    Result of a BNPL eligibility check for a customer and amount.

    ``eligible`` is True if at least one BNPL option is available.
    ``options`` contains all qualifying plans, sorted by provider.
    """

    eligible: bool
    options: tuple[BNPLOption, ...] = field(default=())

    def __post_init__(self) -> None:
        if self.eligible and not self.options:
            raise ValueError("Eligible result must include at least one option")
        if not self.eligible and self.options:
            raise ValueError("Ineligible result must not include options")
