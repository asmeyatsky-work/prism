"""
Agentic CX — Channel Delivery Ports

Architectural Intent:
- Channel ports abstract message delivery across different platforms
- WebChannelPort handles embeddable widget and web API delivery
- WhatsAppChannelPort handles WhatsApp Business API integration
- ChannelAdapterPort is the unified adapter that routes to the correct channel
- All ports are async for non-blocking I/O
"""

from __future__ import annotations

from typing import Any, Protocol

from prism.agentic_cx.domain.value_objects.agent_config import Channel


class WebChannelPort(Protocol):
    """
    Port for delivering messages through the web channel.

    Supports the embeddable chat widget and web API endpoints.
    Delivery is via WebSocket for real-time or HTTP for polling.
    """

    async def send_message(
        self,
        conversation_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Send a message to the customer via the web channel."""
        ...

    async def send_typing_indicator(
        self,
        conversation_id: str,
    ) -> None:
        """Send a typing indicator to show the agent is processing."""
        ...


class WhatsAppChannelPort(Protocol):
    """
    Port for delivering messages through WhatsApp Business API.

    Handles message formatting, template compliance, and media
    attachment constraints specific to WhatsApp.
    """

    async def send_message(
        self,
        phone_number: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Send a text message to the customer via WhatsApp."""
        ...

    async def send_image(
        self,
        phone_number: str,
        image_url: str,
        caption: str = "",
    ) -> None:
        """Send an image message via WhatsApp (e.g. product photo)."""
        ...

    async def send_template(
        self,
        phone_number: str,
        template_name: str,
        parameters: dict[str, str] | None = None,
    ) -> None:
        """Send a pre-approved template message via WhatsApp."""
        ...


class ChannelAdapterPort(Protocol):
    """
    Unified channel adapter that routes messages to the correct delivery port.

    The application layer uses this single port for all channel delivery,
    and the infrastructure adapter handles routing based on channel type.
    """

    async def send(
        self,
        channel: Channel,
        destination: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a message through the appropriate channel.

        Args:
            channel: Target channel (WEB, WHATSAPP, etc.)
            destination: Channel-specific destination (conversation_id, phone number, etc.)
            message: Message content to deliver.
            metadata: Optional channel-specific metadata.
        """
        ...
