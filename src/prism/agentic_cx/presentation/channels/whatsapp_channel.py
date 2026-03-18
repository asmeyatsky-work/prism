"""
Agentic CX — WhatsApp Channel Handler

Architectural Intent:
- Implements WhatsAppChannelPort for WhatsApp Business API integration
- Handles message formatting within WhatsApp constraints (4096 char limit)
- Supports text, image, and template messages
- Template messages are required for initiating conversations (WhatsApp policy)
- Manages phone number formatting and validation
- Integrates with WhatsApp Business API via Cloud API (Meta Graph API)
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class WhatsAppChannel:
    """
    WhatsApp Business API channel handler.

    Manages message delivery through the WhatsApp Cloud API,
    handling formatting constraints, template compliance, and
    media attachments for luxury retail interactions.
    """

    MAX_MESSAGE_LENGTH = 4096
    MAX_CAPTION_LENGTH = 1024

    def __init__(
        self,
        phone_number_id: str = "",
        access_token: str = "",
        api_version: str = "v21.0",
        business_account_id: str = "",
    ) -> None:
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._api_version = api_version
        self._business_account_id = business_account_id
        self._base_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}"

    async def send_message(
        self,
        phone_number: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a text message to the customer via WhatsApp.

        Handles message length constraints by splitting long messages.
        Formats phone numbers to E.164 standard.
        """
        formatted_phone = self._format_phone_number(phone_number)
        if not formatted_phone:
            logger.error("Invalid phone number: %s", phone_number)
            return

        # Split message if it exceeds WhatsApp limit
        chunks = self._split_message(message)
        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "to": formatted_phone,
                "type": "text",
                "text": {"body": chunk},
            }
            await self._send_api_request(payload)

    async def send_image(
        self,
        phone_number: str,
        image_url: str,
        caption: str = "",
    ) -> None:
        """
        Send an image message via WhatsApp.

        Used for product images, virtual try-on results, and
        lookbook recommendations.
        """
        formatted_phone = self._format_phone_number(phone_number)
        if not formatted_phone:
            return

        # Truncate caption if needed
        if len(caption) > self.MAX_CAPTION_LENGTH:
            caption = caption[: self.MAX_CAPTION_LENGTH - 3] + "..."

        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": "image",
            "image": {
                "link": image_url,
                "caption": caption,
            },
        }
        await self._send_api_request(payload)

    async def send_template(
        self,
        phone_number: str,
        template_name: str,
        parameters: dict[str, str] | None = None,
    ) -> None:
        """
        Send a pre-approved template message via WhatsApp.

        Templates are required for re-engaging customers outside the
        24-hour messaging window. Common templates:
        - welcome_greeting: Initial brand greeting
        - order_update: Shipping/delivery notification
        - appointment_reminder: Store visit reminder
        - stylist_recommendation: New product suggestion
        """
        formatted_phone = self._format_phone_number(phone_number)
        if not formatted_phone:
            return

        # Build template components
        components: list[dict[str, Any]] = []
        if parameters:
            body_params = [
                {"type": "text", "text": value}
                for value in parameters.values()
            ]
            components.append({
                "type": "body",
                "parameters": body_params,
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "en"},
                "components": components,
            },
        }
        await self._send_api_request(payload)

    async def send_interactive_buttons(
        self,
        phone_number: str,
        body_text: str,
        buttons: list[dict[str, str]],
    ) -> None:
        """
        Send an interactive button message.

        Used for presenting options like:
        - "View Product" / "Add to Wishlist" / "Book Appointment"
        """
        formatted_phone = self._format_phone_number(phone_number)
        if not formatted_phone:
            return

        # WhatsApp allows max 3 buttons
        wa_buttons = [
            {
                "type": "reply",
                "reply": {
                    "id": btn.get("id", f"btn_{i}"),
                    "title": btn.get("title", "")[:20],  # Max 20 chars
                },
            }
            for i, btn in enumerate(buttons[:3])
        ]

        payload = {
            "messaging_product": "whatsapp",
            "to": formatted_phone,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body_text},
                "action": {"buttons": wa_buttons},
            },
        }
        await self._send_api_request(payload)

    def _split_message(self, message: str) -> list[str]:
        """Split a message into chunks that fit WhatsApp's length limit."""
        if len(message) <= self.MAX_MESSAGE_LENGTH:
            return [message]

        chunks: list[str] = []
        while message:
            if len(message) <= self.MAX_MESSAGE_LENGTH:
                chunks.append(message)
                break

            # Find a natural break point (paragraph, sentence, or word)
            split_at = self.MAX_MESSAGE_LENGTH
            for delimiter in ["\n\n", "\n", ". ", " "]:
                idx = message.rfind(delimiter, 0, self.MAX_MESSAGE_LENGTH)
                if idx > 0:
                    split_at = idx + len(delimiter)
                    break

            chunks.append(message[:split_at].rstrip())
            message = message[split_at:].lstrip()

        return chunks

    @staticmethod
    def _format_phone_number(phone: str) -> str:
        """
        Format a phone number to E.164 standard.

        Strips non-digit characters and ensures the number starts with
        a country code. Returns empty string if invalid.
        """
        digits = re.sub(r"[^\d+]", "", phone)
        if digits.startswith("+"):
            digits = digits[1:]
        digits = re.sub(r"\D", "", digits)

        if len(digits) < 10 or len(digits) > 15:
            return ""
        return digits

    async def _send_api_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Send a request to the WhatsApp Cloud API.

        In production, this uses httpx or aiohttp to call the Meta
        Graph API. For development, it logs the payload.
        """
        logger.info(
            "WhatsApp API request: %s -> %s",
            payload.get("to", "unknown"),
            payload.get("type", "unknown"),
        )
        # Production: POST to self._base_url + "/messages"
        # with Authorization: Bearer {self._access_token}
        return {"messaging_product": "whatsapp", "status": "sent"}
