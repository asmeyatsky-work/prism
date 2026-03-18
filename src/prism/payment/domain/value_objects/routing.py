"""
Payment Domain — Routing Value Objects

Architectural Intent:
- Immutable value objects that model FlowRoute's multi-PSP routing decisions
- RoutingCondition provides a mini-DSL for rule matching (field/operator/value)
- RoutingDecision captures the selected PSP with audit trail
- PSPCapability describes what each payment service provider supports

These are consumed by the RoutingService domain service and stored
alongside Payment aggregates for observability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from prism.shared.domain.value_objects import Currency, ValueObject


class ConditionOperator(str, Enum):
    """Comparison operators for routing rule conditions."""

    EQ = "EQ"
    GT = "GT"
    LT = "LT"
    IN = "IN"
    BETWEEN = "BETWEEN"


@dataclass(frozen=True)
class RoutingCondition(ValueObject):
    """
    A single predicate in a routing rule.

    Examples:
    - RoutingCondition(field="currency", operator=EQ, value="EUR")
    - RoutingCondition(field="amount", operator=BETWEEN, value=(100, 5000))
    - RoutingCondition(field="card_type", operator=IN, value=("visa", "mastercard"))
    """

    field: str
    operator: ConditionOperator
    value: Any

    def matches(self, context: dict[str, Any]) -> bool:
        """Evaluate this condition against a payment context dictionary."""
        actual = context.get(self.field)
        if actual is None:
            return False

        if self.operator == ConditionOperator.EQ:
            return actual == self.value
        if self.operator == ConditionOperator.GT:
            return actual > self.value
        if self.operator == ConditionOperator.LT:
            return actual < self.value
        if self.operator == ConditionOperator.IN:
            return actual in self.value
        if self.operator == ConditionOperator.BETWEEN:
            low, high = self.value
            return low <= actual <= high

        return False


@dataclass(frozen=True)
class RoutingDecision(ValueObject):
    """
    The outcome of FlowRoute's PSP selection algorithm.

    Captures the selected PSP, the reasoning, alternative PSPs for cascade
    failover, and a numeric score for observability and A/B testing.
    """

    selected_psp: str
    reason: str
    alternatives: tuple[str, ...] = field(default=())
    score: float = 0.0

    def __post_init__(self) -> None:
        if not self.selected_psp:
            raise ValueError("selected_psp must not be empty")


@dataclass(frozen=True)
class PSPCapability(ValueObject):
    """
    Describes a PSP's capabilities and performance characteristics.

    Used by the routing engine to match payment requirements against
    available providers. avg_auth_rate is a rolling metric fed from
    the Intelligence context.
    """

    psp_id: str
    supported_currencies: tuple[Currency, ...] = field(default=())
    supported_card_types: tuple[str, ...] = field(default=())
    avg_auth_rate: float = 0.0

    def __post_init__(self) -> None:
        if not self.psp_id:
            raise ValueError("psp_id must not be empty")
        if not (0.0 <= self.avg_auth_rate <= 1.0):
            raise ValueError("avg_auth_rate must be between 0.0 and 1.0")

    def supports_currency(self, currency: Currency) -> bool:
        """Check if this PSP supports a given currency."""
        return currency in self.supported_currencies

    def supports_card_type(self, card_type: str) -> bool:
        """Check if this PSP supports a given card type."""
        return card_type in self.supported_card_types
