"""
Payment Application — Capture Payment Use Case

Architectural Intent:
- Captures a previously authorised payment via the assigned PSP
- Transitions the Payment aggregate from AUTHORISED to CAPTURED
- Emits PaymentCapturedEvent for downstream consumption
- Returns CommandResult with the updated payment status
"""

from __future__ import annotations

from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort

from prism.payment.application.dtos.payment_dto import PaymentResponseDTO
from prism.payment.domain.entities.payment import PaymentStatus
from prism.payment.domain.ports.payment_ports import PaymentRepositoryPort, PSPPort


class CapturePaymentUseCase:
    """
    Capture a previously authorised payment.

    Calls the PSP's capture endpoint, then transitions the aggregate
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
        Capture the payment identified by ``payment_id``.

        Fails if the payment is not in AUTHORISED status or the PSP
        capture call fails.
        """
        payment = await self._payment_repo.get_by_id(payment_id)
        if payment is None:
            return CommandResult.fail(
                f"Payment {payment_id} not found",
                code="PAYMENT_NOT_FOUND",
            )

        if payment.status != PaymentStatus.AUTHORISED:
            return CommandResult.fail(
                f"Payment is {payment.status.value}, expected AUTHORISED",
                code="INVALID_PAYMENT_STATUS",
            )

        # Call PSP capture
        psp_adapter = self._psp_registry.get(payment.psp_id)
        if psp_adapter is None:
            return CommandResult.fail(
                f"PSP adapter '{payment.psp_id}' not found",
                code="PSP_NOT_FOUND",
            )

        try:
            capture_result = await psp_adapter.capture(payment.psp_transaction_id)
        except Exception as exc:
            return CommandResult.fail(
                f"PSP capture failed: {exc}",
                code="PSP_CAPTURE_ERROR",
            )

        if capture_result.get("status") != "captured":
            return CommandResult.fail(
                f"PSP capture returned status: {capture_result.get('status')}",
                code="PSP_CAPTURE_REJECTED",
            )

        # Transition aggregate
        captured_payment = payment.capture()

        # Persist
        await self._payment_repo.save(captured_payment)

        # Dispatch events
        if self._event_bus and captured_payment.domain_events:
            await self._event_bus.publish(list(captured_payment.domain_events))

        response = PaymentResponseDTO(
            payment_id=captured_payment.id,
            order_id=captured_payment.order_id,
            status=captured_payment.status.value,
            psp_id=captured_payment.psp_id,
            psp_transaction_id=captured_payment.psp_transaction_id,
            amount=captured_payment.amount.amount,
            currency=captured_payment.amount.currency.value,
        )

        return CommandResult.ok(response)
