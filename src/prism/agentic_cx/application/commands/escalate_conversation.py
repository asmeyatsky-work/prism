"""
Agentic CX — Escalate Conversation Use Case

Architectural Intent:
- Transfers a conversation from AI agent to human associate
- Builds full escalation context: summary, sentiment, tool history
- Notifies via channel adapter that a human is taking over
- Dispatches ConversationEscalatedEvent for CRM and analytics
- Preserves complete conversation history for seamless handoff
"""

from __future__ import annotations

from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort

from prism.agentic_cx.application.dtos.agent_dto import EscalationDTO
from prism.agentic_cx.domain.entities.conversation import ConversationStatus
from prism.agentic_cx.domain.ports.agent_ports import ConversationRepositoryPort
from prism.agentic_cx.domain.ports.channel_ports import ChannelAdapterPort


class EscalateConversationUseCase:
    """
    Use case: escalate a conversation to a human associate.

    Ensures smooth handoff by building structured context and
    notifying the customer that a human will continue the conversation.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepositoryPort,
        channel_adapter: ChannelAdapterPort,
        event_bus: EventBusPort,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._channel_adapter = channel_adapter
        self._event_bus = event_bus

    async def execute(
        self,
        conversation_id: str,
        reason: str,
        confidence: float = 0.0,
    ) -> CommandResult[EscalationDTO]:
        """
        Execute the escalation use case.

        Steps:
        1. Load conversation from repository
        2. Validate conversation state (must be ACTIVE or PAUSED)
        3. Escalate conversation (state transition + context build)
        4. Notify customer via channel that a human is joining
        5. Persist and dispatch events

        Returns:
            CommandResult containing the EscalationDTO on success.
        """
        # Load conversation
        conversation = await self._conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            return CommandResult.fail(
                f"Conversation not found: {conversation_id}",
                code="NOT_FOUND",
            )

        # Validate state
        if conversation.status not in (
            ConversationStatus.ACTIVE,
            ConversationStatus.PAUSED,
        ):
            return CommandResult.fail(
                f"Cannot escalate conversation in {conversation.status.value} status",
                code="INVALID_STATE",
            )

        # Perform escalation
        conversation = conversation.escalate_to_human(
            reason=reason,
            confidence=confidence,
        )

        # Persist
        await self._conversation_repo.save(conversation)

        # Notify customer
        escalation_message = (
            "I'm connecting you with one of our associates who can "
            "assist you further. They'll have the full context of our "
            "conversation. One moment please."
        )
        await self._channel_adapter.send(
            channel=conversation.channel,
            destination=conversation.conversation_id,
            message=escalation_message,
        )

        # Dispatch events
        events = list(conversation.domain_events)
        if events:
            await self._event_bus.publish(events)

        # Build DTO
        ctx = conversation.escalation_context
        dto = EscalationDTO(
            conversation_id=conversation.conversation_id,
            reason=ctx.reason if ctx else reason,
            confidence=ctx.confidence if ctx else confidence,
            conversation_summary=ctx.conversation_summary if ctx else "",
            customer_sentiment=ctx.customer_sentiment if ctx else "neutral",
            agent_type=conversation.agent_type.value,
            channel=conversation.channel.value,
        )
        return CommandResult.ok(dto)
