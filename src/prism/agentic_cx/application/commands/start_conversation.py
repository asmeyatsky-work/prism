"""
Agentic CX — Start Conversation Use Case

Architectural Intent:
- Creates a new Conversation aggregate for a customer interaction
- Loads customer profile if a customer_id is provided (ContextOps)
- Selects the appropriate agent persona for the tenant and agent type
- Initialises session memory for the new conversation
- Dispatches ConversationStartedEvent via the event bus
- Returns ConversationDTO to the caller
"""

from __future__ import annotations

from typing import Any

from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import DomainEvent, EventBusPort

from prism.agentic_cx.application.dtos.agent_dto import (
    ConversationDTO,
    MessageDTO,
    StartConversationRequestDTO,
)
from prism.agentic_cx.domain.entities.conversation import (
    AgentType,
    Conversation,
    ConversationStatus,
)
from prism.agentic_cx.domain.ports.agent_ports import (
    ConversationRepositoryPort,
    CustomerProfilePort,
)
from prism.agentic_cx.domain.ports.memory_ports import SessionMemoryPort
from prism.agentic_cx.domain.value_objects.agent_config import Channel
from prism.agentic_cx.domain.value_objects.messages import (
    MessageModality,
    MessageRole,
)


class StartConversationUseCase:
    """
    Use case: start a new customer-agent conversation.

    Orchestrates the creation of a conversation aggregate, customer
    profile lookup, session memory initialisation, and event dispatch.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepositoryPort,
        customer_profile_port: CustomerProfilePort,
        session_memory: SessionMemoryPort,
        event_bus: EventBusPort,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._customer_profile_port = customer_profile_port
        self._session_memory = session_memory
        self._event_bus = event_bus

    async def execute(
        self,
        request: StartConversationRequestDTO,
    ) -> CommandResult[ConversationDTO]:
        """
        Execute the start conversation use case.

        Steps:
        1. Check for existing active conversation (prevent duplicates)
        2. Create Conversation aggregate
        3. Load customer profile if customer_id provided
        4. Initialise session memory
        5. Add initial message if provided
        6. Persist and dispatch events

        Returns:
            CommandResult containing the ConversationDTO on success.
        """
        try:
            agent_type = AgentType(request.agent_type)
            channel = Channel(request.channel)
        except ValueError as e:
            return CommandResult.fail(str(e), code="INVALID_INPUT")

        # Check for existing active conversation
        if request.customer_id:
            existing = await self._conversation_repo.get_active_by_customer(
                customer_id=request.customer_id,
                tenant_id=request.tenant_id,
            )
            if existing is not None:
                return CommandResult.fail(
                    f"Customer already has an active conversation: {existing.conversation_id}",
                    code="DUPLICATE_CONVERSATION",
                )

        # Create conversation aggregate
        conversation = Conversation.start(
            tenant_id=request.tenant_id,
            agent_type=agent_type,
            channel=channel,
            customer_id=request.customer_id,
        )

        # Load customer profile for ContextOps
        customer_context: dict[str, Any] = {}
        if request.customer_id:
            profile = await self._customer_profile_port.get_profile(
                customer_id=request.customer_id,
                tenant_id=request.tenant_id,
            )
            if profile:
                customer_context = profile.to_agent_context()
                # Increment conversation count
                updated_profile = profile.increment_conversation_count()
                await self._customer_profile_port.update_profile(updated_profile)

        # Initialise session memory
        await self._session_memory.store(
            session_id=conversation.conversation_id,
            key="customer_context",
            value=customer_context,
        )

        # Add initial customer message if provided
        if request.initial_message:
            conversation = conversation.add_message(
                role=MessageRole.CUSTOMER,
                content=request.initial_message,
                modality=MessageModality.TEXT,
            )

        # Persist
        await self._conversation_repo.save(conversation)

        # Dispatch domain events
        events = list(conversation.domain_events)
        if events:
            await self._event_bus.publish(events)

        # Clear events after dispatch
        conversation = conversation.clear_events()

        # Build DTO
        dto = _to_conversation_dto(conversation)
        return CommandResult.ok(dto)


def _to_conversation_dto(conversation: Conversation) -> ConversationDTO:
    """Convert a Conversation aggregate to a ConversationDTO."""
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
    return ConversationDTO(
        conversation_id=conversation.conversation_id,
        tenant_id=conversation.tenant_id,
        customer_id=conversation.customer_id,
        agent_type=conversation.agent_type.value,
        channel=conversation.channel.value,
        status=conversation.status.value,
        messages=messages,
        started_at=conversation.started_at,
        last_activity_at=conversation.last_activity_at,
    )
