"""
Agentic CX — Memory Ports

Architectural Intent:
- SessionMemoryPort manages per-session short-term context (within a conversation)
- LongTermMemoryPort manages persistent customer preferences across conversations
- Separation allows different storage strategies: in-memory/cache for session,
  Firestore/database for long-term
- Session memory is ephemeral and expires with the conversation
- Long-term memory persists indefinitely and enriches the ContextOps profile
"""

from __future__ import annotations

from typing import Any, Protocol


class SessionMemoryPort(Protocol):
    """
    Short-term session memory for active conversations.

    Stores working context that the agent accumulates during a
    conversation — e.g. items discussed, customer preferences
    expressed in this session, tool call results for reference.

    Session memory is ephemeral and tied to a conversation's lifetime.
    """

    async def store(
        self,
        session_id: str,
        key: str,
        value: Any,
    ) -> None:
        """
        Store a key-value pair in session memory.

        Args:
            session_id: Conversation ID serving as session identifier.
            key: Memory key (e.g. "discussed_products", "budget_range").
            value: Arbitrary serialisable value.
        """
        ...

    async def retrieve(
        self,
        session_id: str,
        key: str,
    ) -> Any:
        """
        Retrieve a value from session memory.

        Returns None if the key does not exist.
        """
        ...

    async def get_session_context(
        self,
        session_id: str,
    ) -> dict[str, Any]:
        """
        Retrieve the entire session context as a dictionary.

        Used to build the LLM context at each conversation turn.
        """
        ...

    async def clear_session(
        self,
        session_id: str,
    ) -> None:
        """Clear all session memory for a completed/expired conversation."""
        ...


class LongTermMemoryPort(Protocol):
    """
    Persistent customer memory across conversations.

    Stores learned preferences, style affinities, and interaction
    patterns that improve the agent's personalisation over time.
    This is a key part of the ContextOps feedback loop.
    """

    async def store_preference(
        self,
        customer_id: str,
        key: str,
        value: Any,
    ) -> None:
        """
        Store a customer preference.

        Overwrites any existing value for the same key.

        Args:
            customer_id: Customer identifier.
            key: Preference key (e.g. "preferred_colors", "avoided_materials").
            value: Preference value.
        """
        ...

    async def get_preferences(
        self,
        customer_id: str,
    ) -> dict[str, Any]:
        """
        Retrieve all stored preferences for a customer.

        Returns an empty dict if no preferences exist.
        """
        ...

    async def delete_preference(
        self,
        customer_id: str,
        key: str,
    ) -> None:
        """Delete a specific preference for a customer."""
        ...
