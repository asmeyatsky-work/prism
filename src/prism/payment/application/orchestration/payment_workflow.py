"""
Payment Application — Payment Workflow (DAG Orchestration)

Architectural Intent:
- Uses DAGOrchestrator from shared kernel for parallelism-first execution
- Step graph: evaluate_routing + fetch_fx_rates run in PARALLEL (no dependency)
- authorise_payment depends on both routing and FX results
- On decline, cascade_retry re-enters the authorisation path
- Per skill2026 Principle 6: independent steps always run concurrently

DAG Topology:
  evaluate_routing ──┐
                     ├──> authorise_payment
  fetch_fx_rates ────┘
"""

from __future__ import annotations

from typing import Any

from prism.shared.application.orchestration import DAGOrchestrator, WorkflowStep

from prism.payment.domain.entities.payment import Payment, PaymentStatus
from prism.payment.domain.ports.payment_ports import (
    FXRatePort,
    PaymentRepositoryPort,
    PSPPort,
    RoutingRuleRepositoryPort,
)
from prism.payment.domain.services.fx_service import FXService
from prism.payment.domain.services.routing_service import RoutingService
from prism.payment.domain.value_objects.routing import PSPCapability


class PaymentWorkflow:
    """
    DAG-based payment processing workflow.

    Orchestrates routing evaluation and FX rate fetching in parallel,
    then authorises the payment, with cascade retry on decline.
    """

    def __init__(
        self,
        psp_registry: dict[str, PSPPort],
        fx_providers: list[FXRatePort],
        routing_rule_repo: RoutingRuleRepositoryPort,
        payment_repo: PaymentRepositoryPort,
        psp_capabilities: list[PSPCapability],
    ) -> None:
        self._psp_registry = psp_registry
        self._fx_providers = fx_providers
        self._routing_rule_repo = routing_rule_repo
        self._payment_repo = payment_repo
        self._psp_capabilities = psp_capabilities
        self._routing_service = RoutingService()
        self._fx_service = FXService()

    async def execute(self, payment: Payment, card_token: str) -> Payment:
        """
        Run the full payment processing workflow.

        1. Evaluate routing + fetch FX rates in parallel (DAG)
        2. Authorise with the selected PSP
        3. On decline, cascade retry if eligible
        """
        # Build workflow context
        context: dict[str, Any] = {
            "payment": payment,
            "card_token": card_token,
            "psp_registry": self._psp_registry,
            "fx_providers": self._fx_providers,
            "routing_rule_repo": self._routing_rule_repo,
            "psp_capabilities": self._psp_capabilities,
            "routing_service": self._routing_service,
            "fx_service": self._fx_service,
        }

        # Define DAG steps
        steps = [
            WorkflowStep(
                name="evaluate_routing",
                execute=_evaluate_routing_step,
                depends_on=(),
                is_critical=True,
                timeout_seconds=10.0,
            ),
            WorkflowStep(
                name="fetch_fx_rates",
                execute=_fetch_fx_rates_step,
                depends_on=(),
                is_critical=False,  # Payment can proceed without FX
                timeout_seconds=15.0,
            ),
            WorkflowStep(
                name="authorise_payment",
                execute=_authorise_payment_step,
                depends_on=("evaluate_routing", "fetch_fx_rates"),
                is_critical=True,
                timeout_seconds=30.0,
            ),
        ]

        orchestrator = DAGOrchestrator(steps)
        results = await orchestrator.execute(context)

        authorise_result = results["authorise_payment"]
        if not authorise_result.success:
            raise RuntimeError(
                f"Payment authorisation failed: {authorise_result.error}"
            )

        result_payment: Payment = authorise_result.value

        # Cascade retry loop if declined
        while result_payment.status == PaymentStatus.DECLINED:
            if not self._routing_service.should_cascade(
                result_payment.decline_reason,
                result_payment.retry_count,
            ):
                break

            routing = result_payment.routing_decision
            if not routing or not routing.alternatives:
                break

            next_psp = self._routing_service.select_cascade_psp(
                current_psp=result_payment.psp_id,
                alternatives=routing.alternatives,
                decline_pattern=result_payment.decline_reason or "",
            )

            result_payment = result_payment.retry_with_cascade(next_psp)
            if result_payment.status == PaymentStatus.FAILED:
                break

            # Attempt authorisation with cascade PSP
            psp_adapter = self._psp_registry.get(next_psp)
            if not psp_adapter:
                break

            psp_result = await psp_adapter.authorise(
                amount=result_payment.amount,
                currency=result_payment.amount.currency,
                card_token=card_token,
            )

            if psp_result.get("status") == "authorised":
                result_payment = result_payment.authorise(psp_result)
            else:
                result_payment = result_payment.decline(
                    psp_result.get("decline_reason", "unknown")
                )

        # Persist final state
        await self._payment_repo.save(result_payment)
        return result_payment


async def _evaluate_routing_step(
    context: dict[str, Any],
    dep_results: dict[str, Any],
) -> Any:
    """DAG step: evaluate FlowRoute routing rules and PSP capabilities."""
    payment: Payment = context["payment"]
    routing_rule_repo: RoutingRuleRepositoryPort = context["routing_rule_repo"]
    routing_service: RoutingService = context["routing_service"]
    psp_capabilities: list[PSPCapability] = context["psp_capabilities"]

    rules = await routing_rule_repo.get_rules(payment.tenant_id)
    decision = routing_service.evaluate_route(payment, rules, psp_capabilities)
    return decision


async def _fetch_fx_rates_step(
    context: dict[str, Any],
    dep_results: dict[str, Any],
) -> Any:
    """DAG step: fetch FX rates from all providers in parallel."""
    import asyncio

    payment: Payment = context["payment"]
    fx_providers: list[FXRatePort] = context["fx_providers"]

    if payment.customer_currency == payment.settlement_currency:
        return None  # No FX needed

    tasks = [
        provider.get_rate(payment.customer_currency, payment.settlement_currency)
        for provider in fx_providers
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    rates = [r for r in results if not isinstance(r, BaseException)]

    if not rates:
        return None

    fx_service: FXService = context["fx_service"]
    return fx_service.select_best_rate(rates)


async def _authorise_payment_step(
    context: dict[str, Any],
    dep_results: dict[str, Any],
) -> Any:
    """DAG step: authorise payment with the selected PSP."""
    payment: Payment = context["payment"]
    psp_registry: dict[str, Any] = context["psp_registry"]
    card_token: str = context["card_token"]

    routing_decision = dep_results.get("evaluate_routing")
    fx_rate = dep_results.get("fetch_fx_rates")

    if routing_decision is None:
        raise RuntimeError("Routing decision is required for authorisation")

    # Apply routing decision and optional FX rate
    payment = payment.begin_authorisation(routing_decision)
    if fx_rate is not None:
        payment = payment.with_fx_rate(fx_rate)

    # Call the PSP
    psp_adapter = psp_registry.get(routing_decision.selected_psp)
    if psp_adapter is None:
        raise RuntimeError(
            f"PSP adapter not found for '{routing_decision.selected_psp}'"
        )

    psp_result = await psp_adapter.authorise(
        amount=payment.amount,
        currency=payment.amount.currency,
        card_token=card_token,
    )

    if psp_result.get("status") == "authorised":
        return payment.authorise(psp_result)
    else:
        return payment.decline(psp_result.get("decline_reason", "unknown"))
