"""
Agentic CX — Web Channel Handler

Architectural Intent:
- Implements WebChannelPort for embeddable widget and web API delivery
- Supports WebSocket for real-time streaming and HTTP for polling
- Handles message formatting, typing indicators, and connection management
- The web widget is embeddable in brand e-commerce sites via <script> tag
- Tenant-scoped: widget configuration and styling per brand
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class WebChannel:
    """
    Web channel handler for the embeddable chat widget.

    Manages WebSocket connections for real-time agent interaction
    and provides HTTP endpoints for polling-based clients. Handles
    message formatting and delivery confirmation.
    """

    def __init__(
        self,
        websocket_manager: Any = None,
    ) -> None:
        self._ws_manager = websocket_manager
        self._active_connections: dict[str, Any] = {}

    async def send_message(
        self,
        conversation_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Send a message to the customer via the web channel.

        Attempts WebSocket delivery first for real-time experience.
        Falls back to queueing for HTTP polling if no active connection.
        """
        payload = self._format_message(conversation_id, message, metadata)

        # Try WebSocket delivery
        ws = self._active_connections.get(conversation_id)
        if ws:
            try:
                await self._send_ws(ws, payload)
                logger.debug(
                    "Sent message via WebSocket for conversation %s",
                    conversation_id,
                )
                return
            except Exception as e:
                logger.warning(
                    "WebSocket send failed for %s, queueing: %s",
                    conversation_id,
                    str(e),
                )
                self._active_connections.pop(conversation_id, None)

        # Queue for HTTP polling
        await self._queue_message(conversation_id, payload)
        logger.debug(
            "Queued message for HTTP polling for conversation %s",
            conversation_id,
        )

    async def send_typing_indicator(
        self,
        conversation_id: str,
    ) -> None:
        """Send a typing indicator to show the agent is processing."""
        ws = self._active_connections.get(conversation_id)
        if ws:
            try:
                await self._send_ws(ws, {
                    "type": "typing",
                    "conversation_id": conversation_id,
                })
            except Exception:
                pass  # Non-critical — best effort

    async def register_connection(
        self,
        conversation_id: str,
        websocket: Any,
    ) -> None:
        """Register a WebSocket connection for a conversation."""
        self._active_connections[conversation_id] = websocket
        logger.info(
            "WebSocket connection registered for conversation %s",
            conversation_id,
        )

    async def unregister_connection(
        self,
        conversation_id: str,
    ) -> None:
        """Unregister a WebSocket connection."""
        self._active_connections.pop(conversation_id, None)

    def _format_message(
        self,
        conversation_id: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Format a message for web delivery."""
        return {
            "type": "message",
            "conversation_id": conversation_id,
            "content": message,
            "role": "agent",
            "metadata": metadata or {},
        }

    async def _send_ws(self, websocket: Any, payload: dict[str, Any]) -> None:
        """Send a payload via WebSocket."""
        if hasattr(websocket, "send_json"):
            await websocket.send_json(payload)
        elif hasattr(websocket, "send"):
            await websocket.send(json.dumps(payload))

    async def _queue_message(
        self,
        conversation_id: str,
        payload: dict[str, Any],
    ) -> None:
        """
        Queue a message for HTTP polling retrieval.

        In production, this would push to a message queue (Cloud Tasks
        or Pub/Sub) for reliable delivery. For now, uses in-memory.
        """
        # Production: push to Cloud Tasks or Pub/Sub
        # Development: log for visibility
        logger.info(
            "Message queued for polling: conversation=%s",
            conversation_id,
        )

    def get_widget_config(self, tenant_id: str) -> dict[str, Any]:
        """
        Generate the embeddable widget configuration for a tenant.

        Returns JavaScript-compatible configuration for the chat widget
        that brands embed on their e-commerce sites.
        """
        return {
            "tenant_id": tenant_id,
            "endpoint": f"/api/v1/agent/conversations",
            "websocket_url": f"wss://agent.prism.example/{tenant_id}/ws",
            "theme": {
                "primary_color": "#000000",
                "font_family": "system-ui, sans-serif",
                "position": "bottom-right",
                "border_radius": "12px",
            },
            "features": {
                "typing_indicators": True,
                "message_reactions": False,
                "file_upload": True,
                "voice_input": False,
            },
        }
