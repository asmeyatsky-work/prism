"""
Payment Infrastructure — Planet Payment PSP Adapter

Architectural Intent:
- Implements PSPPort protocol for Planet Payment processing
- Planet Payment specialises in multi-currency and DCC for luxury retail
- Translates domain-level authorise/capture/refund calls into Planet's API
- Particularly strong for AED, SAR, and cross-border luxury transactions
- All responses are normalised to the PSPPort return contract

Production Note:
- In production, this would use Planet Payment's REST/SOAP API via httpx
- Planet's DCC capability is exposed separately via the FX rate port
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from prism.shared.domain.value_objects import Currency, Money

logger = logging.getLogger(__name__)


class PlanetPaymentAdapter:
    """
    Planet Payment PSP adapter implementing the PSPPort protocol.

    Provides authorise, capture, and refund operations against Planet's API.
    Optimised for cross-border luxury retail transactions.
    """

    def __init__(
        self,
        merchant_id: str,
        api_key: str,
        api_base_url: str = "https://api.planetpayment.com/v1",
    ) -> None:
        self._merchant_id = merchant_id
        self._api_key = api_key
        self._api_base_url = api_base_url

    @property
    def psp_id(self) -> str:
        return "planet_payment"

    async def authorise(
        self,
        amount: Money,
        currency: Currency,
        card_token: str,
    ) -> dict[str, Any]:
        """
        Request payment authorisation from Planet Payment.

        Planet Payment's authorisation supports DCC at the point of auth,
        making it ideal for cross-currency luxury purchases.
        """
        logger.info(
            "Planet Payment authorise: amount=%s %s, merchant=%s",
            amount.amount,
            currency.value,
            self._merchant_id,
        )

        transaction_id = f"pp_{uuid4().hex[:24]}"

        return {
            "transaction_id": transaction_id,
            "status": "authorised",
            "psp": "planet_payment",
            "raw_response": {
                "transactionId": transaction_id,
                "merchantId": self._merchant_id,
                "amount": amount.amount,
                "currency": currency.value,
                "responseCode": "00",
                "responseMessage": "Approved",
            },
        }

    async def capture(self, transaction_id: str) -> dict[str, Any]:
        """
        Capture a previously authorised Planet Payment transaction.
        """
        logger.info("Planet Payment capture: transaction_id=%s", transaction_id)

        return {
            "status": "captured",
            "capture_id": f"ppc_{uuid4().hex[:24]}",
            "psp": "planet_payment",
        }

    async def refund(
        self,
        transaction_id: str,
        amount: Money,
    ) -> dict[str, Any]:
        """
        Refund a captured Planet Payment transaction.
        """
        logger.info(
            "Planet Payment refund: transaction_id=%s, amount=%s",
            transaction_id,
            amount.amount,
        )

        return {
            "status": "refunded",
            "refund_id": f"ppr_{uuid4().hex[:24]}",
            "psp": "planet_payment",
        }
