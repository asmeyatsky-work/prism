"""
Payment Application — Process Payment Use Case

Architectural Intent:
- Orchestrates the full payment processing flow via DAGOrchestrator
- Steps: evaluate_routing + fetch_fx_rates (parallel) -> authorise_payment
- On decline, cascade_retry is handled by the PaymentWorkflow
- Returns CommandResult with PaymentResponseDTO on success or failure
- Domain events are collected on the aggregate and dispatched after persistence

This is the primary write use case for the Payment bounded context.
"""

from __future__ import annotations

from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort
from prism.shared.domain.value_objects import Currency, Money

from prism.payment.application.dtos.payment_dto import PaymentRequestDTO, PaymentResponseDTO
from prism.payment.application.orchestration.payment_workflow import PaymentWorkflow
from prism.payment.domain.entities.payment import Payment
from prism.payment.domain.ports.payment_ports import (
    FXRatePort,
    PaymentRepositoryPort,
    PSPPort,
    RoutingRuleRepositoryPort,
)
from prism.payment.domain.value_objects.routing import PSPCapability


class ProcessPaymentUseCase:
    """
    Process a payment through the FlowRoute orchestration pipeline.

    Parallel FX rate fetching and routing evaluation run concurrently
    via the DAGOrchestrator. The result includes full audit trail with
    routing decision, FX rate, and PSP transaction details.
    """

    def __init__(
        self,
        psp_registry: dict[str, PSPPort],
        fx_providers: list[FXRatePort],
        routing_rule_repo: RoutingRuleRepositoryPort,
        payment_repo: PaymentRepositoryPort,
        psp_capabilities: list[PSPCapability],
        event_bus: EventBusPort | None = None,
    ) -> None:
        self._psp_registry = psp_registry
        self._fx_providers = fx_providers
        self._routing_rule_repo = routing_rule_repo
        self._payment_repo = payment_repo
        self._psp_capabilities = psp_capabilities
        self._event_bus = event_bus

    async def execute(self, request: PaymentRequestDTO) -> CommandResult[PaymentResponseDTO]:
        """
        Execute the payment processing workflow.

        Returns CommandResult.ok with PaymentResponseDTO on success,
        or CommandResult.fail with error details on failure.
        """
        try:
            # Parse currencies
            payment_currency = Currency(request.currency)
            customer_currency = Currency(request.customer_currency)
            settlement_currency = Currency(request.settlement_currency)
        except ValueError as exc:
            return CommandResult.fail(
                f"Invalid currency: {exc}",
                code="INVALID_CURRENCY",
            )

        # Create Payment aggregate
        payment = Payment.create(
            order_id=request.order_id,
            tenant_id=request.tenant_id,
            amount=Money(amount=request.amount, currency=payment_currency),
            customer_currency=customer_currency,
            settlement_currency=settlement_currency,
        )

        # Run the orchestrated workflow
        workflow = PaymentWorkflow(
            psp_registry=self._psp_registry,
            fx_providers=self._fx_providers,
            routing_rule_repo=self._routing_rule_repo,
            payment_repo=self._payment_repo,
            psp_capabilities=self._psp_capabilities,
        )

        try:
            result_payment = await workflow.execute(payment, request.card_token)
        except Exception as exc:
            return CommandResult.fail(str(exc), code="PAYMENT_PROCESSING_ERROR")

        # Dispatch domain events
        if self._event_bus and result_payment.domain_events:
            await self._event_bus.publish(list(result_payment.domain_events))

        # Build response DTO
        response = PaymentResponseDTO(
            payment_id=result_payment.id,
            order_id=result_payment.order_id,
            status=result_payment.status.value,
            psp_id=result_payment.psp_id,
            psp_transaction_id=result_payment.psp_transaction_id,
            amount=result_payment.amount.amount,
            currency=result_payment.amount.currency.value,
            decline_reason=result_payment.decline_reason,
            retry_count=result_payment.retry_count,
        )

        return CommandResult.ok(response)
