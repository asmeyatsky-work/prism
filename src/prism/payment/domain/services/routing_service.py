"""
Payment Domain — FlowRoute Routing Service

Architectural Intent:
- Pure domain service with no infrastructure dependencies
- Evaluates tenant-scoped routing rules against payment context
- Falls back to PSP capability scoring when no rules match
- Implements cascade retry logic (should_cascade, select_cascade_psp)
- Scoring formula: auth_rate * currency_match * card_match

FlowRoute Algorithm:
1. Sort rules by priority, evaluate conditions
2. If a rule matches, select its target PSP
3. If no rule matches, score PSP capabilities and pick the best
4. Always compute alternatives for cascade failover
"""

from __future__ import annotations

from prism.payment.domain.entities.payment import Payment
from prism.payment.domain.entities.routing_rule import RoutingRule
from prism.payment.domain.value_objects.routing import PSPCapability, RoutingDecision

# Decline reasons that are retryable via cascade (different PSP may succeed)
_RETRYABLE_DECLINE_REASONS = frozenset({
    "insufficient_funds",
    "processor_declined",
    "do_not_honor",
    "try_again_later",
    "network_error",
    "timeout",
})

# Maximum cascade retries
_MAX_CASCADE_RETRIES = 3


class RoutingService:
    """
    FlowRoute domain service — selects the optimal PSP for a payment.

    Pure domain logic: no I/O, no async, no infrastructure coupling.
    """

    @staticmethod
    def evaluate_route(
        payment: Payment,
        rules: list[RoutingRule],
        psp_capabilities: list[PSPCapability],
    ) -> RoutingDecision:
        """
        Select the best PSP for the given payment.

        Strategy:
        1. Evaluate rules in priority order; first match wins.
        2. If no rule matches, score capabilities and select the best.
        3. Always populate alternatives for cascade failover.
        """
        payment_context = _build_payment_context(payment)

        # Phase 1: Rule-based routing
        sorted_rules = sorted(
            (r for r in rules if r.enabled),
            key=lambda r: r.priority,
        )
        for rule in sorted_rules:
            if rule.matches(payment_context):
                alternatives = _rank_alternatives(
                    exclude_psp=rule.target_psp,
                    psp_capabilities=psp_capabilities,
                    payment=payment,
                )
                return RoutingDecision(
                    selected_psp=rule.target_psp,
                    reason=f"Matched rule '{rule.name}' (priority {rule.priority})",
                    alternatives=alternatives,
                    score=1.0,
                )

        # Phase 2: Capability-based scoring
        if not psp_capabilities:
            raise ValueError("No PSP capabilities available for routing")

        scored = [
            (cap.psp_id, _score_psp(cap, payment))
            for cap in psp_capabilities
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        best_psp, best_score = scored[0]
        alternatives = tuple(psp_id for psp_id, _ in scored[1:])

        return RoutingDecision(
            selected_psp=best_psp,
            reason="Capability-based scoring (no rule matched)",
            alternatives=alternatives,
            score=best_score,
        )

    @staticmethod
    def should_cascade(decline_reason: str | None, retry_count: int) -> bool:
        """
        Determine whether a declined payment should be retried with another PSP.

        Retries are permitted only for specific decline reasons and within
        the retry budget.
        """
        if retry_count >= _MAX_CASCADE_RETRIES:
            return False
        if not decline_reason:
            return False
        return decline_reason.lower() in _RETRYABLE_DECLINE_REASONS

    @staticmethod
    def select_cascade_psp(
        current_psp: str,
        alternatives: tuple[str, ...],
        decline_pattern: str,
    ) -> str:
        """
        Select the next PSP for a cascade retry.

        Simple round-robin through alternatives. The decline_pattern parameter
        is available for future intelligent cascade selection based on
        historical decline analysis.
        """
        available = [psp for psp in alternatives if psp != current_psp]
        if not available:
            raise ValueError("No alternative PSPs available for cascade")
        return available[0]


def _build_payment_context(payment: Payment) -> dict:
    """Build a flat dictionary from a Payment for rule condition evaluation."""
    return {
        "currency": payment.amount.currency.value,
        "amount": payment.amount.amount,
        "customer_currency": payment.customer_currency.value,
        "settlement_currency": payment.settlement_currency.value,
        "tenant_id": payment.tenant_id,
    }


def _score_psp(capability: PSPCapability, payment: Payment) -> float:
    """
    Score a PSP based on its capabilities relative to a payment.

    Formula: auth_rate * currency_bonus * card_bonus
    - currency_bonus: 1.2 if supported, 0.3 if not
    - card_bonus: 1.0 (no card info on Payment aggregate — placeholder)
    """
    currency_match = 1.2 if capability.supports_currency(payment.amount.currency) else 0.3
    return capability.avg_auth_rate * currency_match


def _rank_alternatives(
    exclude_psp: str,
    psp_capabilities: list[PSPCapability],
    payment: Payment,
) -> tuple[str, ...]:
    """Rank remaining PSPs by score for cascade failover ordering."""
    scored = [
        (cap.psp_id, _score_psp(cap, payment))
        for cap in psp_capabilities
        if cap.psp_id != exclude_psp
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return tuple(psp_id for psp_id, _ in scored)
