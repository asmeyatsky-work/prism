"""
Agentic CX — Agent Configuration Value Objects

Architectural Intent:
- AgentToolkit defines which tools an agent persona has access to
- ChannelConfig captures per-channel capability constraints
- Both are frozen dataclasses for safe sharing across threads
- Tool names reference MCP tool identifiers from other PRISM bounded contexts
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from prism.shared.domain.value_objects import ValueObject


class Channel(str, Enum):
    """Supported customer interaction channels."""

    WEB = "WEB"
    MOBILE_APP = "MOBILE_APP"
    WHATSAPP = "WHATSAPP"
    WECHAT = "WECHAT"


@dataclass(frozen=True)
class AgentToolkit(ValueObject):
    """
    Set of MCP tools available to an agent persona.

    Tool names correspond to registered MCP tool identifiers across
    PRISM bounded contexts (catalogue, discovery, tryon, payment, OMS).

    Standard tools:
    - catalogue_search: Product search via Catalogue BC
    - virtual_tryon: AI try-on via Visual Discovery BC
    - inventory_check: Real-time stock via Commerce BC
    - wishlist_manage: Wishlist CRUD via Commerce BC
    - appointment_book: In-store appointment via CRM BC
    - associate_escalate: Human handoff via Agentic CX BC
    - order_status: Order tracking via OMS BC
    - returns: Returns initiation via OMS BC
    - gift_wrapping: Gift services via Commerce BC
    """

    available_tools: tuple[str, ...] = ()

    def has_tool(self, tool_name: str) -> bool:
        """Check whether a specific tool is available in this toolkit."""
        return tool_name in self.available_tools

    def tool_count(self) -> int:
        """Return the number of tools in this toolkit."""
        return len(self.available_tools)

    def merge(self, other: AgentToolkit) -> AgentToolkit:
        """Combine two toolkits, deduplicating tool names."""
        combined = set(self.available_tools) | set(other.available_tools)
        return AgentToolkit(available_tools=tuple(sorted(combined)))


@dataclass(frozen=True)
class ChannelConfig(ValueObject):
    """
    Capability constraints for a specific interaction channel.

    Different channels have different limitations: WhatsApp caps message
    length, WeChat supports voice but not arbitrary images, etc.
    These constraints are enforced at the presentation layer before
    agent responses are delivered.
    """

    channel: Channel
    max_message_length: int = 4096
    supports_images: bool = True
    supports_voice: bool = False

    def __post_init__(self) -> None:
        if self.max_message_length <= 0:
            raise ValueError("Max message length must be positive")
