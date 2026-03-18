"""Domain entities for the Agentic CX bounded context."""

from prism.agentic_cx.domain.entities.agent_persona import AgentPersona
from prism.agentic_cx.domain.entities.conversation import Conversation
from prism.agentic_cx.domain.entities.customer_profile import CustomerProfile

__all__ = ["AgentPersona", "Conversation", "CustomerProfile"]
