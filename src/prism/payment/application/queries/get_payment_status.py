"""
Payment Application — Get Payment Status Query

Architectural Intent:
- Read-side query returning the current status of a payment
- No state mutation — pure read from the repository
- Returns QueryResult with PaymentResponseDTO
"""

from __future__ import annotations

from prism.shared.application.dtos import QueryResult

from prism.payment.application.dtos.payment_dto import PaymentResponseDTO
from prism.payment.domain.ports.payment_ports import PaymentRepositoryPort


class GetPaymentStatusQuery:
    """
    Retrieve the current status and details of a payment.

    Supports lookup by either payment_id or order_id.
    """

    def __init__(self, payment_repo: PaymentRepositoryPort) -> None:
        self._payment_repo = payment_repo

    async def execute(
        self,
        payment_id: str | None = None,
        order_id: str | None = None,
    ) -> QueryResult[PaymentResponseDTO]:
        """
        Fetch payment status by payment_id or order_id.

        Exactly one of the two parameters must be provided.
        """
        if not payment_id and not order_id:
            return QueryResult.fail("Either payment_id or order_id must be provided")

        if payment_id:
            payment = await self._payment_repo.get_by_id(payment_id)
        else:
            payment = await self._payment_repo.get_by_order_id(order_id)  # type: ignore[arg-type]

        if payment is None:
            return QueryResult.fail("Payment not found")

        response = PaymentResponseDTO(
            payment_id=payment.id,
            order_id=payment.order_id,
            status=payment.status.value,
            psp_id=payment.psp_id,
            psp_transaction_id=payment.psp_transaction_id,
            amount=payment.amount.amount,
            currency=payment.amount.currency.value,
            decline_reason=payment.decline_reason,
            retry_count=payment.retry_count,
        )

        return QueryResult.ok(response)
