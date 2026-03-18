"""
Agentic CX — MCP Server (SynapticBridge)

Architectural Intent:
- The core MCP server for the Agentic CX bounded context
- Exposes agent capabilities as MCP tools for cross-context integration
- Provides resources for conversation and customer profile access
- Includes prompt templates for common agent interactions
- Per skill2026 Principle 5: MCP-Native Integration Architecture
- Transport: stdio for local, SSE for deployed

Tools (write operations):
- start_conversation: Begin a new customer-agent conversation
- send_message: Send a customer message and get agent response
- escalate: Escalate conversation to human associate
- get_recommendations: Get product recommendations based on context

Resources (read operations):
- agent://conversation/{id}: Conversation state and history
- agent://customer/{customer_id}/profile: Customer profile data

Prompts (reusable templates):
- stylist_greeting: Brand-voice greeting for new conversations
- outfit_recommendation: Structured recommendation prompt
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class AgenticCXServer:
    """
    MCP server for the Agentic CX bounded context.

    Implements the SynapticBridge pattern: exposing AI agent capabilities
    as MCP tools that other bounded contexts and external clients can invoke.
    """

    def __init__(
        self,
        start_conversation_use_case: Any,
        handle_message_use_case: Any,
        escalate_use_case: Any,
        get_conversation_query: Any,
        get_customer_profile_query: Any,
    ) -> None:
        self._start_conversation = start_conversation_use_case
        self._handle_message = handle_message_use_case
        self._escalate = escalate_use_case
        self._get_conversation = get_conversation_query
        self._get_customer_profile = get_customer_profile_query

    # ── Tool Definitions ─────────────────────────────────────────────

    def list_tools(self) -> list[dict[str, Any]]:
        """Return the list of MCP tool definitions."""
        return [
            {
                "name": "start_conversation",
                "description": (
                    "Start a new customer-agent conversation for a luxury brand. "
                    "Creates a conversation with the appropriate agent persona "
                    "(Personal Stylist or Commerce Concierge)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tenant_id": {
                            "type": "string",
                            "description": "Brand/tenant identifier (e.g. 'gucci', 'burberry')",
                        },
                        "agent_type": {
                            "type": "string",
                            "enum": ["PERSONAL_STYLIST", "COMMERCE_CONCIERGE"],
                            "description": "Type of agent to handle the conversation",
                        },
                        "channel": {
                            "type": "string",
                            "enum": ["WEB", "MOBILE_APP", "WHATSAPP", "WECHAT"],
                            "description": "Customer interaction channel",
                        },
                        "customer_id": {
                            "type": "string",
                            "description": "Optional customer identifier for personalisation",
                        },
                        "initial_message": {
                            "type": "string",
                            "description": "Optional first message from the customer",
                        },
                    },
                    "required": ["tenant_id", "agent_type", "channel"],
                },
            },
            {
                "name": "send_message",
                "description": (
                    "Send a customer message to an active conversation and receive "
                    "the AI agent's response. The agent may use tools (catalogue search, "
                    "virtual try-on, etc.) to formulate its response."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "conversation_id": {
                            "type": "string",
                            "description": "Active conversation identifier",
                        },
                        "content": {
                            "type": "string",
                            "description": "Customer message content",
                        },
                        "modality": {
                            "type": "string",
                            "enum": ["TEXT", "IMAGE", "VOICE"],
                            "default": "TEXT",
                            "description": "Message content type",
                        },
                    },
                    "required": ["conversation_id", "content"],
                },
            },
            {
                "name": "escalate",
                "description": (
                    "Escalate a conversation from AI agent to human associate. "
                    "Transfers full conversation context for seamless handoff."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "conversation_id": {
                            "type": "string",
                            "description": "Conversation to escalate",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for escalation",
                        },
                    },
                    "required": ["conversation_id", "reason"],
                },
            },
            {
                "name": "get_recommendations",
                "description": (
                    "Get AI-powered product recommendations based on conversation "
                    "context, customer profile, and current interaction."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "conversation_id": {
                            "type": "string",
                            "description": "Conversation for context",
                        },
                        "category": {
                            "type": "string",
                            "description": "Product category filter (optional)",
                        },
                        "max_results": {
                            "type": "integer",
                            "default": 5,
                            "description": "Maximum number of recommendations",
                        },
                    },
                    "required": ["conversation_id"],
                },
            },
        ]

    # ── Tool Handlers ────────────────────────────────────────────────

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Handle an MCP tool call.

        Routes to the appropriate use case based on tool name.
        """
        handlers = {
            "start_conversation": self._handle_start_conversation,
            "send_message": self._handle_send_message,
            "escalate": self._handle_escalate,
            "get_recommendations": self._handle_get_recommendations,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return await handler(arguments)
        except Exception as e:
            logger.error("Tool call '%s' failed: %s", name, str(e))
            return {"error": str(e)}

    async def _handle_start_conversation(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle start_conversation tool call."""
        from prism.agentic_cx.application.dtos.agent_dto import (
            StartConversationRequestDTO,
        )

        request = StartConversationRequestDTO(
            tenant_id=args["tenant_id"],
            agent_type=args.get("agent_type", "PERSONAL_STYLIST"),
            channel=args.get("channel", "WEB"),
            customer_id=args.get("customer_id", ""),
            initial_message=args.get("initial_message", ""),
        )
        result = await self._start_conversation.execute(request)
        if result.success and result.value:
            return result.value.model_dump()
        return {"error": result.error or "Failed to start conversation"}

    async def _handle_send_message(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle send_message tool call."""
        from prism.agentic_cx.application.dtos.agent_dto import SendMessageRequestDTO

        request = SendMessageRequestDTO(
            conversation_id=args["conversation_id"],
            content=args["content"],
            modality=args.get("modality", "TEXT"),
        )
        result = await self._handle_message.execute(request)
        if result.success and result.value:
            return result.value.model_dump()
        return {"error": result.error or "Failed to handle message"}

    async def _handle_escalate(self, args: dict[str, Any]) -> dict[str, Any]:
        """Handle escalate tool call."""
        result = await self._escalate.execute(
            conversation_id=args["conversation_id"],
            reason=args.get("reason", "Customer requested human assistance"),
        )
        if result.success and result.value:
            return result.value.model_dump()
        return {"error": result.error or "Failed to escalate"}

    async def _handle_get_recommendations(
        self, args: dict[str, Any]
    ) -> dict[str, Any]:
        """Handle get_recommendations tool call."""
        # Retrieve conversation for context
        result = await self._get_conversation.by_id(args["conversation_id"])
        if not result.success or not result.data:
            return {"error": "Conversation not found"}

        # In production, this would call the recommendation engine
        # via the catalogue MCP server with conversation context
        return {
            "recommendations": [
                {
                    "product_id": "prod_001",
                    "name": "Recommended based on conversation context",
                    "reason": "Matches discussed style preferences",
                }
            ],
            "conversation_id": args["conversation_id"],
        }

    # ── Resource Definitions ─────────────────────────────────────────

    def list_resources(self) -> list[dict[str, Any]]:
        """Return the list of MCP resource definitions."""
        return [
            {
                "uri": "agent://conversation/{id}",
                "name": "Conversation",
                "description": "Full conversation state and message history",
                "mimeType": "application/json",
            },
            {
                "uri": "agent://customer/{customer_id}/profile",
                "name": "Customer Profile",
                "description": "Customer profile with preferences and history",
                "mimeType": "application/json",
            },
        ]

    async def read_resource(self, uri: str) -> dict[str, Any]:
        """
        Handle an MCP resource read.

        Parses the URI to determine the resource type and ID,
        then retrieves the data via the appropriate query.
        """
        if uri.startswith("agent://conversation/"):
            conversation_id = uri.split("/")[-1]
            result = await self._get_conversation.by_id(conversation_id)
            if result.success and result.data:
                return result.data.model_dump()
            return {"error": "Conversation not found"}

        if uri.startswith("agent://customer/") and uri.endswith("/profile"):
            parts = uri.split("/")
            customer_id = parts[3]  # agent://customer/{id}/profile
            # Tenant ID would come from request context in production
            result = await self._get_customer_profile.execute(
                customer_id=customer_id,
                tenant_id="",  # Would be resolved from MCP request context
            )
            if result.success and result.data:
                return result.data.model_dump()
            return {"error": "Customer profile not found"}

        return {"error": f"Unknown resource: {uri}"}

    # ── Prompt Definitions ───────────────────────────────────────────

    def list_prompts(self) -> list[dict[str, Any]]:
        """Return the list of MCP prompt templates."""
        return [
            {
                "name": "stylist_greeting",
                "description": "Brand-voice greeting for a new styling conversation",
                "arguments": [
                    {
                        "name": "brand_name",
                        "description": "The luxury brand name",
                        "required": True,
                    },
                    {
                        "name": "persona_name",
                        "description": "The stylist persona name",
                        "required": True,
                    },
                    {
                        "name": "customer_name",
                        "description": "Customer name if known",
                        "required": False,
                    },
                ],
            },
            {
                "name": "outfit_recommendation",
                "description": "Structured prompt for outfit recommendation generation",
                "arguments": [
                    {
                        "name": "occasion",
                        "description": "The occasion (e.g. evening gala, casual brunch)",
                        "required": True,
                    },
                    {
                        "name": "style_preferences",
                        "description": "Customer style preferences",
                        "required": False,
                    },
                    {
                        "name": "budget_range",
                        "description": "Budget range (e.g. '$1000-$3000')",
                        "required": False,
                    },
                ],
            },
        ]

    def get_prompt(
        self, name: str, arguments: dict[str, str]
    ) -> dict[str, Any]:
        """
        Render an MCP prompt template with the given arguments.

        Returns a structured prompt message suitable for LLM consumption.
        """
        if name == "stylist_greeting":
            return self._render_stylist_greeting(arguments)
        if name == "outfit_recommendation":
            return self._render_outfit_recommendation(arguments)
        return {"error": f"Unknown prompt: {name}"}

    def _render_stylist_greeting(
        self, arguments: dict[str, str]
    ) -> dict[str, Any]:
        """Render the stylist greeting prompt."""
        brand = arguments.get("brand_name", "our brand")
        persona = arguments.get("persona_name", "your stylist")
        customer = arguments.get("customer_name", "")

        if customer:
            greeting = (
                f"Welcome back to {brand}, {customer}. I'm {persona}, "
                f"your personal stylist. It's wonderful to see you again. "
                f"How may I assist you today?"
            )
        else:
            greeting = (
                f"Welcome to {brand}. I'm {persona}, your personal stylist. "
                f"I'm here to help you discover something extraordinary. "
                f"What brings you in today?"
            )

        return {
            "messages": [
                {"role": "assistant", "content": {"type": "text", "text": greeting}}
            ]
        }

    def _render_outfit_recommendation(
        self, arguments: dict[str, str]
    ) -> dict[str, Any]:
        """Render the outfit recommendation prompt."""
        occasion = arguments.get("occasion", "a special occasion")
        preferences = arguments.get("style_preferences", "")
        budget = arguments.get("budget_range", "")

        prompt_parts = [
            f"The customer is looking for an outfit for {occasion}.",
        ]
        if preferences:
            prompt_parts.append(f"Style preferences: {preferences}.")
        if budget:
            prompt_parts.append(f"Budget range: {budget}.")
        prompt_parts.extend([
            "",
            "Please recommend a complete outfit including:",
            "1. A key piece (dress, suit, or statement item)",
            "2. Complementary accessories",
            "3. Footwear suggestion",
            "4. Why this combination works for the occasion",
            "",
            "Use the catalogue_search tool to find specific products.",
        ])

        return {
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": "\n".join(prompt_parts)},
                }
            ]
        }


def create_mcp_server_config() -> dict[str, Any]:
    """
    Create the MCP server configuration for registration
    with the shared MCPServerRegistry.
    """
    return {
        "name": "agentic_cx",
        "module": "prism.agentic_cx.infrastructure.mcp_servers.agentic_cx_server",
        "description": (
            "SynapticBridge: Intelligent Agent Platform for luxury retail. "
            "Provides AI-powered Personal Stylist and Commerce Concierge "
            "agents with multi-channel delivery."
        ),
        "transport": "stdio",
        "tools": (
            "start_conversation",
            "send_message",
            "escalate",
            "get_recommendations",
        ),
        "resources": (
            "agent://conversation/{id}",
            "agent://customer/{customer_id}/profile",
        ),
    }
