"""
Agentic CX — Commerce Concierge Agent

Architectural Intent:
- Pre-configured agent for transactional and service conversations
- Configures tools: order_status, returns, appointment_booking, gift_wrapping
- Handles post-purchase interactions: tracking, returns, exchanges
- Integrates with OMS and CRM bounded contexts via Apigee
- Maintains luxury service standards even for operational queries

Interaction Patterns:
- Order inquiry -> tracking details -> delivery management
- Return request -> eligibility check -> label generation
- Gift services -> wrapping options -> personalization
- Store appointment -> availability -> confirmation
"""

from __future__ import annotations

from typing import Any

from prism.agentic_cx.domain.entities.agent_persona import AgentPersona, PersonaTone
from prism.agentic_cx.domain.entities.conversation import AgentType
from prism.agentic_cx.domain.value_objects.agent_config import AgentToolkit


# Standard toolkit for Commerce Concierge agents
COMMERCE_CONCIERGE_TOOLKIT = AgentToolkit(
    available_tools=(
        "order_status",
        "returns",
        "appointment_book",
        "gift_wrapping",
        "inventory_check",
        "catalogue_search",
        "associate_escalate",
    )
)


class CommerceConciergeAgent:
    """
    Pre-configured Commerce Concierge agent.

    Handles transactional and service-oriented customer interactions:
    order tracking, returns/exchanges, gift services, and appointment
    booking. Maintains luxury-grade service quality throughout
    operational conversations.
    """

    def __init__(
        self,
        persona: AgentPersona,
        toolkit: AgentToolkit | None = None,
    ) -> None:
        if persona.agent_type != AgentType.COMMERCE_CONCIERGE:
            raise ValueError(
                f"CommerceConciergeAgent requires COMMERCE_CONCIERGE persona, "
                f"got {persona.agent_type.value}"
            )
        self._persona = persona
        self._toolkit = toolkit or COMMERCE_CONCIERGE_TOOLKIT

    @property
    def persona(self) -> AgentPersona:
        return self._persona

    @property
    def toolkit(self) -> AgentToolkit:
        return self._toolkit

    def build_system_prompt(
        self,
        customer_context: dict[str, Any] | None = None,
    ) -> str:
        """
        Build the full system prompt for the Commerce Concierge.

        Extends the base persona prompt with concierge-specific instructions
        for order management, returns, and service interactions.
        """
        additional = self._build_concierge_instructions(customer_context)
        return self._persona.build_system_prompt(additional_context=additional)

    def _build_concierge_instructions(
        self,
        customer_context: dict[str, Any] | None = None,
    ) -> str:
        """Build concierge-specific instructions for the system prompt."""
        parts = [
            "CONCIERGE CAPABILITIES:",
            "- Track order status and provide delivery updates",
            "- Initiate and manage returns and exchanges",
            "- Book in-store appointments for personal shopping or pickups",
            "- Arrange gift wrapping and personalization services",
            "- Check product availability across channels",
            "- Search the catalogue for replacement or exchange items",
            "",
            "SERVICE PRINCIPLES:",
            "- Treat every operational query as an opportunity to delight",
            "- Proactively offer solutions before the customer asks",
            "- For returns, express understanding and focus on finding the right fit",
            "- Always confirm details before taking action",
            "- Offer alternatives when the requested option is unavailable",
            "",
            "INTERACTION FLOW:",
            "1. Identify the customer's service need quickly",
            "2. Retrieve relevant information (order, return, appointment)",
            "3. Present clear options with luxury-grade communication",
            "4. Confirm the customer's choice before executing",
            "5. Provide follow-up details (tracking, confirmation, next steps)",
            "6. Offer additional assistance or complementary services",
        ]

        if customer_context:
            if customer_context.get("has_purchase_history"):
                recent = customer_context.get("recent_purchases", [])
                if recent:
                    parts.extend([
                        "",
                        f"RECENT ORDERS: {', '.join(recent[-3:])}",
                        "Reference these when the customer asks about orders.",
                    ])

        return "\n".join(parts)

    @staticmethod
    def create_default_personas() -> dict[str, AgentPersona]:
        """
        Create default concierge personas for common luxury brands.

        Concierge personas tend to be more formal and service-oriented
        compared to stylist personas.
        """
        return {
            "gucci": AgentPersona(
                tenant_id="gucci",
                agent_type=AgentType.COMMERCE_CONCIERGE,
                brand_name="Gucci",
                persona_name="Marco",
                tone=PersonaTone.LUXURY,
                greeting_template=(
                    "Welcome to {brand_name} Client Services. I'm {persona_name}, "
                    "your dedicated concierge. How may I assist you today?"
                ),
                style_guidelines=(
                    "Maintain the highest standard of service excellence. "
                    "Be efficient yet never rushed. Every interaction should "
                    "reinforce the Gucci client experience."
                ),
                escalation_threshold=0.2,
            ),
            "burberry": AgentPersona(
                tenant_id="burberry",
                agent_type=AgentType.COMMERCE_CONCIERGE,
                brand_name="Burberry",
                persona_name="James",
                tone=PersonaTone.CONTEMPORARY,
                greeting_template=(
                    "Hello! Welcome to {brand_name} Client Care. I'm {persona_name}. "
                    "I'm here to help with anything you need."
                ),
                style_guidelines=(
                    "Blend British warmth with efficient service. "
                    "Be clear and helpful while maintaining brand prestige."
                ),
                escalation_threshold=0.25,
            ),
        }
