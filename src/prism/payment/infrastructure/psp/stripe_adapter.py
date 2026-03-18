"""
Payment Infrastructure — Stripe PSP Adapter

Architectural Intent:
- Implements PSPPort protocol for Stripe payment processing
- Translates domain-level authorise/capture/refund calls into Stripe API calls
- Uses httpx for async HTTP communication with Stripe's API
- Sensitive credentials are injected via constructor (never hard-coded)
- All responses are normalised to the PSPPort return contract

Production Note:
- In production, this would use the stripe-python SDK with async support
- Error mapping translates Stripe error codes to domain-level decline reasons
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from prism.shared.domain.value_objects import Currency, Money

logger = logging.getLogger(__name__)

# Stripe decline code -> domain decline reason mapping
_STRIPE_DECLINE_MAP: dict[str, str] = {
    "card_declined": "processor_declined",
    "insufficient_funds": "insufficient_funds",
    "lost_card": "lost_or_stolen_card",
    "stolen_card": "lost_or_stolen_card",
    "expired_card": "expired_card",
    "incorrect_cvc": "incorrect_cvc",
    "processing_error": "processor_declined",
    "do_not_honor": "do_not_honor",
}


class StripeAdapter:
    """
    Stripe PSP adapter implementing the PSPPort protocol.

    Provides authorise, capture, and refund operations against Stripe's API.
    In this implementation, API calls are stubbed for development/testing;
    replace with actual httpx/stripe-python calls in production.
    """

    def __init__(
        self,
        api_key: str,
        api_base_url: str = "https://api.stripe.com/v1",
        webhook_secret: str = "",
    ) -> None:
        self._api_key = api_key
        self._api_base_url = api_base_url
        self._webhook_secret = webhook_secret

    @property
    def psp_id(self) -> str:
        return "stripe"

    async def authorise(
        self,
        amount: Money,
        currency: Currency,
        card_token: str,
    ) -> dict[str, Any]:
        """
        Request payment authorisation from Stripe.

        Creates a PaymentIntent with capture_method=manual for two-step
        auth-then-capture flow used in luxury retail.
        """
        logger.info(
            "Stripe authorise: amount=%s %s, token=%s",
            amount.amount,
            currency.value,
            card_token[:8] + "...",
        )

        # In production: httpx POST to /v1/payment_intents
        # Stubbed response for development
        transaction_id = f"pi_{uuid4().hex[:24]}"

        return {
            "transaction_id": transaction_id,
            "status": "authorised",
            "psp": "stripe",
            "raw_response": {
                "id": transaction_id,
                "object": "payment_intent",
                "amount": int(amount.amount * 100),  # Stripe uses cents
                "currency": currency.value.lower(),
                "status": "requires_capture",
            },
        }

    async def capture(self, transaction_id: str) -> dict[str, Any]:
        """
        Capture a previously authorised Stripe PaymentIntent.
        """
        logger.info("Stripe capture: transaction_id=%s", transaction_id)

        return {
            "status": "captured",
            "capture_id": f"ch_{uuid4().hex[:24]}",
            "psp": "stripe",
        }

    async def refund(
        self,
        transaction_id: str,
        amount: Money,
    ) -> dict[str, Any]:
        """
        Refund a captured Stripe payment.
        """
        logger.info(
            "Stripe refund: transaction_id=%s, amount=%s",
            transaction_id,
            amount.amount,
        )

        return {
            "status": "refunded",
            "refund_id": f"re_{uuid4().hex[:24]}",
            "psp": "stripe",
        }

    @staticmethod
    def map_decline_reason(stripe_decline_code: str) -> str:
        """Map a Stripe decline code to a domain-level decline reason."""
        return _STRIPE_DECLINE_MAP.get(stripe_decline_code, "processor_declined")
