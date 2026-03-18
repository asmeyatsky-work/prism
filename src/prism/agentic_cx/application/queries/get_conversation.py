"""
Agentic CX — Get Conversation Query

Architectural Intent:
- Read-only query to retrieve conversation state
- Returns ConversationDTO without mutating any state
- Supports retrieval by conversation ID or by active customer
"""

from __future__ import annotations

from prism.shared.application.dtos import QueryResult

from prism.agentic_cx.application.dtos.agent_dto import (
    AgentToolCallDTO,
    ConversationDTO,
    MessageDTO,
)
from prism.agentic_cx.domain.entities.conversation import Conversation
from prism.agentic_cx.domain.ports.agent_ports import ConversationRepositoryPort


class GetConversationQuery:
    """Query: retrieve a conversation by ID or by active customer."""

    def __init__(self, conversation_repo: ConversationRepositoryPort) -> None:
        self._conversation_repo = conversation_repo

    async def by_id(self, conversation_id: str) -> QueryResult[ConversationDTO]:
        """Retrieve a conversation by its unique identifier."""
        conversation = await self._conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            return QueryResult.fail(f"Conversation not found: {conversation_id}")
        return QueryResult.ok(_to_dto(conversation))

    async def active_by_customer(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> QueryResult[ConversationDTO]:
        """Retrieve the active conversation for a customer."""
        conversation = await self._conversation_repo.get_active_by_customer(
            customer_id=customer_id,
            tenant_id=tenant_id,
        )
        if conversation is None:
            return QueryResult.empty()
        return QueryResult.ok(_to_dto(conversation))


def _to_dto(conversation: Conversation) -> ConversationDTO:
    """Convert a Conversation aggregate to its DTO representation."""
    messages = [
        MessageDTO(
            role=m.role.value,
            content=m.content,
            modality=m.modality.value,
            timestamp=m.timestamp,
            metadata=m.metadata,
        )
        for m in conversation.messages
    ]
    tool_calls = [
        AgentToolCallDTO(
            tool_name=tc.tool_name,
            arguments=tc.arguments,
            result=tc.result,
            duration_ms=tc.duration_ms,
            success=tc.success,
        )
        for tc in conversation.tool_calls
    ]
    return ConversationDTO(
        conversation_id=conversation.conversation_id,
        tenant_id=conversation.tenant_id,
        customer_id=conversation.customer_id,
        agent_type=conversation.agent_type.value,
        channel=conversation.channel.value,
        status=conversation.status.value,
        messages=messages,
        tool_calls=tool_calls,
        started_at=conversation.started_at,
        last_activity_at=conversation.last_activity_at,
    )
