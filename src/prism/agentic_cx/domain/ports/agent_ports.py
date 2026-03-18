"""
Agentic CX — Agent Domain Ports

Architectural Intent:
- Protocol-based ports define the boundary between domain and infrastructure
- AgentLLMPort abstracts the LLM provider (Gemini, Claude, etc.)
- ToolExecutionPort abstracts MCP tool invocation across bounded contexts
- Repository and profile ports follow standard DDD repository pattern
- All ports are async-first for parallelism-first architecture (skill2026 Rule 6)
"""

from __future__ import annotations

from typing import Any, Protocol

from prism.agentic_cx.domain.entities.conversation import Conversation
from prism.agentic_cx.domain.entities.customer_profile import CustomerProfile


class AgentLLMPort(Protocol):
    """
    Port for LLM inference.

    Abstracts the language model provider so the domain layer is
    decoupled from any specific AI service. Implementations handle
    prompt construction, tool formatting, and response parsing.
    """

    async def generate_response(
        self,
        context: dict[str, Any],
        tools: list[dict[str, Any]],
    ) -> str:
        """
        Generate an agent response given conversation context and available tools.

        Args:
            context: Conversation context including history, customer profile,
                     system prompt, and session memory.
            tools: List of tool definitions in MCP-compatible format.

        Returns:
            The agent's text response to the customer.
        """
        ...


class ToolExecutionPort(Protocol):
    """
    Port for executing tools via MCP.

    Each tool call is routed to the appropriate PRISM MCP server
    (catalogue, discovery, tryon, payment, OMS). The infrastructure
    adapter handles server discovery and transport.
    """

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a tool and return its result.

        Args:
            tool_name: MCP tool identifier (e.g. "catalogue_search").
            arguments: Tool arguments as a dictionary.

        Returns:
            Tool execution result as a dictionary.

        Raises:
            ToolExecutionError: If the tool call fails.
        """
        ...


class ConversationRepositoryPort(Protocol):
    """
    Repository port for Conversation aggregate persistence.

    Follows the DDD repository pattern: aggregates are stored and
    retrieved as complete objects. Domain events on the aggregate
    are dispatched by the application layer after successful save.
    """

    async def save(self, conversation: Conversation) -> None:
        """Persist a conversation aggregate (create or update)."""
        ...

    async def get_by_id(self, conversation_id: str) -> Conversation | None:
        """Retrieve a conversation by its unique ID."""
        ...

    async def get_active_by_customer(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> Conversation | None:
        """
        Retrieve the currently active conversation for a customer.

        Returns None if no active conversation exists.
        Only one active conversation per customer is allowed.
        """
        ...


class CustomerProfilePort(Protocol):
    """
    Port for customer profile retrieval and updates.

    The profile may come from a CRM system, a dedicated customer
    data platform, or the Agentic CX internal store.
    """

    async def get_profile(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> CustomerProfile | None:
        """Retrieve a customer profile. Returns None if not found."""
        ...

    async def update_profile(self, profile: CustomerProfile) -> None:
        """Persist updated customer profile."""
        ...
