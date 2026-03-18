"""
Payment Domain — RoutingRule Entity

Architectural Intent:
- Tenant-scoped routing rules for FlowRoute's PSP selection
- Each rule contains a tuple of RoutingConditions evaluated against payment context
- Rules are prioritised (lower number = higher priority) and can be disabled
- The RoutingService iterates rules in priority order to select the best PSP
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prism.shared.domain.entities import Entity

from prism.payment.domain.value_objects.routing import RoutingCondition


@dataclass(frozen=True)
class RoutingRule(Entity):
    """
    A tenant-scoped routing rule for FlowRoute PSP selection.

    Conditions are evaluated conjunctively (all must match).
    Rules are ordered by priority — lower number means higher priority.
    """

    tenant_id: str = ""
    name: str = ""
    conditions: tuple[RoutingCondition, ...] = field(default=())
    target_psp: str = ""
    priority: int = 0
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("RoutingRule name must not be empty")
        if not self.target_psp:
            raise ValueError("RoutingRule target_psp must not be empty")

    def matches(self, context: dict[str, Any]) -> bool:
        """
        Evaluate all conditions against a payment context.

        Returns True only if ALL conditions match (logical AND).
        A rule with no conditions matches everything.
        """
        if not self.enabled:
            return False
        return all(condition.matches(context) for condition in self.conditions)
