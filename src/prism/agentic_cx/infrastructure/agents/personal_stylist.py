"""
Agentic CX — Personal Stylist Agent

Architectural Intent:
- Pre-configured agent for fashion/style advisory conversations
- Configures tools: catalogue_search, virtual_tryon, inventory_check, wishlist_manage
- Builds brand-voice system prompts for luxury stylist persona
- Manages the stylist-specific interaction patterns:
  discovery -> recommendation -> try-on -> purchase consideration
- Integrates with Catalogue and Visual Discovery bounded contexts

Persona Examples:
- "Sofia" for Gucci — LUXURY tone, Italian heritage emphasis
- "Emma" for Burberry — CONTEMPORARY tone, British craftsmanship focus
- "Yuki" for Comme des Garcons — AVANT_GARDE tone, conceptual design language
"""

from __future__ import annotations

from typing import Any

from prism.agentic_cx.domain.entities.agent_persona import AgentPersona, PersonaTone
from prism.agentic_cx.domain.entities.conversation import AgentType
from prism.agentic_cx.domain.value_objects.agent_config import AgentToolkit


# Standard toolkit for Personal Stylist agents
PERSONAL_STYLIST_TOOLKIT = AgentToolkit(
    available_tools=(
        "catalogue_search",
        "virtual_tryon",
        "inventory_check",
        "wishlist_manage",
        "appointment_book",
        "associate_escalate",
    )
)


class PersonalStylistAgent:
    """
    Pre-configured Personal Stylist agent.

    Provides brand-voice styling advice, product recommendations,
    virtual try-on facilitation, and wishlist management. The stylist
    guides customers through a discovery-to-purchase journey with
    personalised recommendations based on their profile.
    """

    def __init__(
        self,
        persona: AgentPersona,
        toolkit: AgentToolkit | None = None,
    ) -> None:
        if persona.agent_type != AgentType.PERSONAL_STYLIST:
            raise ValueError(
                f"PersonalStylistAgent requires PERSONAL_STYLIST persona, "
                f"got {persona.agent_type.value}"
            )
        self._persona = persona
        self._toolkit = toolkit or PERSONAL_STYLIST_TOOLKIT

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
        Build the full system prompt for the Personal Stylist.

        Extends the base persona prompt with stylist-specific instructions
        for product recommendation, style advice, and try-on facilitation.
        """
        additional = self._build_stylist_instructions(customer_context)
        return self._persona.build_system_prompt(additional_context=additional)

    def _build_stylist_instructions(
        self,
        customer_context: dict[str, Any] | None = None,
    ) -> str:
        """Build stylist-specific instructions for the system prompt."""
        parts = [
            "STYLIST CAPABILITIES:",
            "- Search and recommend products from the brand catalogue",
            "- Facilitate virtual try-on experiences for visual validation",
            "- Check real-time inventory across stores and online",
            "- Manage the customer's wishlist for later consideration",
            "- Book in-store appointments with human stylists",
            "",
            "INTERACTION FLOW:",
            "1. Understand the customer's occasion, mood, or style goal",
            "2. Recommend products that match their profile and preferences",
            "3. Offer virtual try-on for visual confidence",
            "4. Check availability and suggest alternatives if needed",
            "5. Help with wishlist curation or purchase decision",
            "6. Offer to book an in-store appointment for hands-on experience",
        ]

        if customer_context:
            style_tags = customer_context.get("style_tags", [])
            if style_tags:
                parts.extend([
                    "",
                    f"CUSTOMER STYLE PROFILE: {', '.join(style_tags)}",
                ])
            if customer_context.get("is_returning"):
                parts.extend([
                    "",
                    "This is a returning customer. Reference their previous "
                    "interactions and known preferences to provide continuity.",
                ])

        return "\n".join(parts)

    @staticmethod
    def create_default_personas() -> dict[str, AgentPersona]:
        """
        Create default stylist personas for common luxury brands.

        These serve as templates that tenants can customise.
        """
        return {
            "gucci": AgentPersona(
                tenant_id="gucci",
                agent_type=AgentType.PERSONAL_STYLIST,
                brand_name="Gucci",
                persona_name="Sofia",
                tone=PersonaTone.LUXURY,
                greeting_template=(
                    "Buongiorno! Welcome to {brand_name}. I'm {persona_name}, "
                    "your personal stylist. How may I help you discover something "
                    "extraordinary today?"
                ),
                style_guidelines=(
                    "Emphasize Italian craftsmanship and Gucci heritage. "
                    "Reference the creative director's vision when relevant. "
                    "Use warm, inviting language with a touch of Italian flair."
                ),
                escalation_threshold=0.25,
            ),
            "burberry": AgentPersona(
                tenant_id="burberry",
                agent_type=AgentType.PERSONAL_STYLIST,
                brand_name="Burberry",
                persona_name="Emma",
                tone=PersonaTone.CONTEMPORARY,
                greeting_template=(
                    "Hello and welcome to {brand_name}. I'm {persona_name}, "
                    "here to help you explore our collection. "
                    "What brings you in today?"
                ),
                style_guidelines=(
                    "Balance British heritage with modern innovation. "
                    "Reference the iconic check pattern and outerwear legacy "
                    "while showcasing contemporary design evolution."
                ),
                escalation_threshold=0.3,
            ),
            "balenciaga": AgentPersona(
                tenant_id="balenciaga",
                agent_type=AgentType.PERSONAL_STYLIST,
                brand_name="Balenciaga",
                persona_name="Alex",
                tone=PersonaTone.AVANT_GARDE,
                greeting_template=(
                    "Welcome to {brand_name}. I'm {persona_name}. "
                    "Let's find something that makes a statement."
                ),
                style_guidelines=(
                    "Embrace bold, unconventional aesthetics. "
                    "Reference architectural silhouettes and deconstructed design. "
                    "Encourage creative expression and daring choices."
                ),
                escalation_threshold=0.35,
            ),
        }
