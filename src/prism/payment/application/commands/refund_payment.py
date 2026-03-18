"""
Payment Application — Refund Payment Use Case

Architectural Intent:
- Refunds a previously captured payment via the assigned PSP
- Transitions the Payment aggregate from CAPTURED to REFUNDED
- Emits PaymentRefundedEvent for BARQ reconciliation and Commerce return processing
- Returns CommandResult with the updated payment status
"""

from __future__ import annotations

from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort

from prism.payment.application.dtos.payment_dto import PaymentResponseDTO
from prism.payment.domain.entities.payment import PaymentStatus
from prism.payment.domain.ports.payment_ports import PaymentRepositoryPort, PSPPort


class RefundPaymentUseCase:
    """
    Refund a previously captured payment.

    Calls the PSP's refund endpoint, then transitions the aggregate
    and dispatches the resulting domain events.
    """

    def __init__(
        self,
        psp_registry: dict[str, PSPPort],
        payment_repo: PaymentRepositoryPort,
        event_bus: EventBusPort | None = None,
    ) -> None:
        self._psp_registry = psp_registry
        self._payment_repo = payment_repo
        self._event_bus = event_bus

    async def execute(self, payment_id: str) -> CommandResult[PaymentResponseDTO]:
        """
        Refund the payment identified by ``payment_id``.

        Fails if the payment is not in CAPTURED status or the PSP
        refund call fails.
        """
        payment = await self._payment_repo.get_by_id(payment_id)
        if payment is None:
            return CommandResult.fail(
                f"Payment {payment_id} not found",
                code="PAYMENT_NOT_FOUND",
            )

        if payment.status != PaymentStatus.CAPTURED:
            return CommandResult.fail(
                f"Payment is {payment.status.value}, expected CAPTURED",
                code="INVALID_PAYMENT_STATUS",
            )

        # Call PSP refund
        psp_adapter = self._psp_registry.get(payment.psp_id)
        if psp_adapter is None:
            return CommandResult.fail(
                f"PSP adapter '{payment.psp_id}' not found",
                code="PSP_NOT_FOUND",
            )

        try:
            refund_result = await psp_adapter.refund(
                transaction_id=payment.psp_transaction_id,
                amount=payment.amount,
            )
        except Exception as exc:
            return CommandResult.fail(
                f"PSP refund failed: {exc}",
                code="PSP_REFUND_ERROR",
            )

        if refund_result.get("status") != "refunded":
            return CommandResult.fail(
                f"PSP refund returned status: {refund_result.get('status')}",
                code="PSP_REFUND_REJECTED",
            )

        # Transition aggregate
        refunded_payment = payment.refund()

        # Persist
        await self._payment_repo.save(refunded_payment)

        # Dispatch events
        if self._event_bus and refunded_payment.domain_events:
            await self._event_bus.publish(list(refunded_payment.domain_events))

        response = PaymentResponseDTO(
            payment_id=refunded_payment.id,
            order_id=refunded_payment.order_id,
            status=refunded_payment.status.value,
            psp_id=refunded_payment.psp_id,
            psp_transaction_id=refunded_payment.psp_transaction_id,
            amount=refunded_payment.amount.amount,
            currency=refunded_payment.amount.currency.value,
        )

        return CommandResult.ok(response)
