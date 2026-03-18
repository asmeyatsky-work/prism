"""
Agentic CX — Agent Persona Entity

Architectural Intent:
- AgentPersona defines the brand-voice personality of an AI agent
- Each tenant (brand) configures one or more personas for their agents
- Tone governs language style: LUXURY for heritage brands (Hermes, Chanel),
  CONTEMPORARY for modern luxury (Balenciaga), AVANT_GARDE for cutting-edge
- Escalation threshold is the confidence floor below which the agent
  hands off to a human associate
- Greeting template and style guidelines are injected into the LLM system prompt
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from prism.shared.domain.entities import Entity

from prism.agentic_cx.domain.entities.conversation import AgentType


class PersonaTone(str, Enum):
    """Brand voice tone for agent communication style."""

    LUXURY = "LUXURY"
    CONTEMPORARY = "CONTEMPORARY"
    AVANT_GARDE = "AVANT_GARDE"


@dataclass(frozen=True)
class AgentPersona(Entity):
    """
    Brand-voice configuration for an AI agent persona.

    Each luxury brand on PRISM configures its own persona — e.g.
    "Sofia" for Gucci's Personal Stylist or "James" for Burberry's
    Commerce Concierge. The persona governs tone, greeting style,
    and the confidence threshold at which the agent escalates to
    a human associate.
    """

    tenant_id: str = ""
    agent_type: AgentType = AgentType.PERSONAL_STYLIST
    brand_name: str = ""
    persona_name: str = ""
    tone: PersonaTone = PersonaTone.LUXURY
    greeting_template: str = (
        "Welcome to {brand_name}. I'm {persona_name}, your personal stylist. "
        "How may I assist you today?"
    )
    style_guidelines: str = ""
    escalation_threshold: float = 0.3

    def __post_init__(self) -> None:
        if not 0.0 <= self.escalation_threshold <= 1.0:
            raise ValueError("Escalation threshold must be between 0.0 and 1.0")

    def render_greeting(self) -> str:
        """Render the greeting template with persona variables."""
        return self.greeting_template.format(
            brand_name=self.brand_name,
            persona_name=self.persona_name,
        )

    def build_system_prompt(self, additional_context: str = "") -> str:
        """
        Build the LLM system prompt incorporating brand voice and guidelines.

        This prompt is injected at the start of every LLM call to ensure
        the agent maintains consistent brand personality throughout.
        """
        tone_instructions = {
            PersonaTone.LUXURY: (
                "Communicate with refined elegance and understated sophistication. "
                "Use formal but warm language. Reference heritage and craftsmanship. "
                "Never use slang or overly casual expressions."
            ),
            PersonaTone.CONTEMPORARY: (
                "Be approachable yet polished. Balance modern language with "
                "brand prestige. Show enthusiasm while maintaining professionalism."
            ),
            PersonaTone.AVANT_GARDE: (
                "Be bold, creative, and forward-thinking in your communication. "
                "Embrace unconventional perspectives. Inspire the customer with "
                "daring style choices while remaining respectful."
            ),
        }
        parts = [
            f"You are {self.persona_name}, the {self.agent_type.value.replace('_', ' ').title()} "
            f"for {self.brand_name}.",
            "",
            f"TONE: {tone_instructions[self.tone]}",
        ]
        if self.style_guidelines:
            parts.extend(["", f"STYLE GUIDELINES: {self.style_guidelines}"])
        if additional_context:
            parts.extend(["", f"CONTEXT: {additional_context}"])
        parts.extend([
            "",
            "RULES:",
            "- Always address the customer with respect and warmth.",
            "- Never disclose that you are an AI unless directly asked.",
            "- If uncertain about a recommendation, acknowledge it honestly.",
            "- Protect customer privacy — never reference other customers.",
            f"- If your confidence drops below {self.escalation_threshold:.0%}, "
            "offer to connect the customer with a human associate.",
        ])
        return "\n".join(parts)
