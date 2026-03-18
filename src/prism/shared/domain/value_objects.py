"""
Shared Domain — Value Objects

Architectural Intent:
- Immutable value objects for concepts without identity
- Money and Currency are shared across Payment, Commerce, and Catalogue contexts
- TenantId enforces multi-tenancy at the domain level
- All value objects are frozen dataclasses — equality is structural
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class ValueObject:
    """Base value object — identity is defined by all field values."""

    pass


class Currency(str, Enum):
    """ISO 4217 currencies relevant to luxury retail markets."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CHF = "CHF"
    JPY = "JPY"
    CNY = "CNY"
    AED = "AED"
    SAR = "SAR"
    HKD = "HKD"
    SGD = "SGD"
    AUD = "AUD"
    KRW = "KRW"


@dataclass(frozen=True)
class Money(ValueObject):
    """Monetary value with currency — used across payment, commerce, and catalogue."""

    amount: float
    currency: Currency

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")

    def add(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} and {other.currency}")
        return Money(amount=round(self.amount + other.amount, 2), currency=self.currency)

    def subtract(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract {self.currency} and {other.currency}")
        result = round(self.amount - other.amount, 2)
        if result < 0:
            raise ValueError("Resulting amount cannot be negative")
        return Money(amount=result, currency=self.currency)

    def multiply(self, factor: float) -> Money:
        return Money(amount=round(self.amount * factor, 2), currency=self.currency)

    def apply_discount(self, percentage: float) -> Money:
        if percentage < 0 or percentage > 100:
            raise ValueError("Discount must be between 0 and 100")
        return Money(
            amount=round(self.amount * (1 - percentage / 100), 2),
            currency=self.currency,
        )


@dataclass(frozen=True)
class TenantId(ValueObject):
    """
    Multi-tenant identifier — scopes all data to a brand.

    Every aggregate and query in PRISM is tenant-scoped. This value object
    ensures tenant isolation is enforced at the domain level, not just
    infrastructure.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not self.value.strip():
            raise ValueError("TenantId cannot be empty")


@dataclass(frozen=True)
class Locale(ValueObject):
    """Language/region locale for luxury market localisation."""

    language: str  # ISO 639-1 (en, fr, it, zh, ar)
    region: str = ""  # ISO 3166-1 alpha-2 (US, FR, IT, CN)

    @property
    def code(self) -> str:
        if self.region:
            return f"{self.language}-{self.region}"
        return self.language


@dataclass(frozen=True)
class ImageRef(ValueObject):
    """Reference to a binary asset in Cloud Storage."""

    bucket: str
    path: str
    content_type: str = "image/jpeg"

    @property
    def gcs_uri(self) -> str:
        return f"gs://{self.bucket}/{self.path}"
