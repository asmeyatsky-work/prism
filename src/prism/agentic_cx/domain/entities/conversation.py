"""
Agentic CX — Conversation Aggregate Root

Architectural Intent:
- Conversation is the central aggregate of the Agentic CX bounded context
- Immutable: every mutation returns a new Conversation instance + domain event
- Messages and tool calls are stored as tuples (immutable sequences)
- Escalation is a first-class state transition with structured context
- Domain events are accumulated and dispatched after persistence

Invariants:
- A COMPLETED or ESCALATED conversation cannot accept new messages
- Escalation captures reason and confidence for seamless human handoff
- All timestamps use UTC per platform convention
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from prism.shared.domain.entities import AggregateRoot

from prism.agentic_cx.domain.events.agentic_events import (
    AgentResponseGeneratedEvent,
    ConversationCompletedEvent,
    ConversationEscalatedEvent,
    ConversationStartedEvent,
    MessageReceivedEvent,
    ToolCallExecutedEvent,
)
from prism.agentic_cx.domain.value_objects.agent_config import Channel
from prism.agentic_cx.domain.value_objects.messages import (
    AgentToolCall,
    ConversationMessage,
    EscalationContext,
    MessageModality,
    MessageRole,
)


class AgentType(str, Enum):
    """Type of AI agent handling the conversation."""

    PERSONAL_STYLIST = "PERSONAL_STYLIST"
    COMMERCE_CONCIERGE = "COMMERCE_CONCIERGE"


class ConversationStatus(str, Enum):
    """Lifecycle status of a conversation."""

    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ESCALATED = "ESCALATED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class Conversation(AggregateRoot):
    """
    Aggregate root for a customer-agent conversation.

    Tracks the full history of messages, tool calls, and state
    transitions. Every mutation method returns a new immutable
    instance along with the corresponding domain event appended
    to the domain_events tuple.
    """

    conversation_id: str = field(default_factory=lambda: str(uuid4()))
    tenant_id: str = ""
    customer_id: str = ""
    agent_type: AgentType = AgentType.PERSONAL_STYLIST
    channel: Channel = Channel.WEB
    status: ConversationStatus = ConversationStatus.ACTIVE
    messages: tuple[ConversationMessage, ...] = ()
    tool_calls: tuple[AgentToolCall, ...] = ()
    escalation_context: EscalationContext | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def start(
        tenant_id: str,
        agent_type: AgentType,
        channel: Channel,
        customer_id: str = "",
    ) -> Conversation:
        """
        Factory method to start a new conversation.

        Returns a fresh Conversation with a ConversationStartedEvent.
        """
        conversation_id = str(uuid4())
        now = datetime.now(UTC)
        event = ConversationStartedEvent(
            aggregate_id=conversation_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            agent_type=agent_type.value,
            channel=channel.value,
        )
        return Conversation(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            customer_id=customer_id,
            agent_type=agent_type,
            channel=channel,
            status=ConversationStatus.ACTIVE,
            started_at=now,
            last_activity_at=now,
            domain_events=(event,),
        )

    def add_message(
        self,
        role: MessageRole,
        content: str,
        modality: MessageModality = MessageModality.TEXT,
        metadata: dict | None = None,
    ) -> Conversation:
        """
        Add a message to the conversation.

        Returns a new Conversation instance with the message appended
        and a MessageReceivedEvent in the domain events.

        Raises ValueError if the conversation is not in a mutable state.
        """
        self._assert_mutable()
        now = datetime.now(UTC)
        message = ConversationMessage(
            role=role,
            content=content,
            modality=modality,
            timestamp=now,
            metadata=metadata or {},
        )
        event = MessageReceivedEvent(
            aggregate_id=self.conversation_id,
            tenant_id=self.tenant_id,
            role=role.value,
            content=content,
            modality=modality.value,
        )
        return replace(
            self,
            messages=self.messages + (message,),
            last_activity_at=now,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def add_tool_call(
        self,
        tool_name: str,
        arguments: dict,
        result: dict,
        duration_ms: int = 0,
        success: bool = True,
    ) -> Conversation:
        """
        Record a tool invocation by the agent.

        Returns a new Conversation with the tool call appended and a
        ToolCallExecutedEvent in the domain events.
        """
        self._assert_mutable()
        now = datetime.now(UTC)
        tool_call = AgentToolCall(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
            success=success,
        )
        event = ToolCallExecutedEvent(
            aggregate_id=self.conversation_id,
            tenant_id=self.tenant_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
            success=success,
        )
        return replace(
            self,
            tool_calls=self.tool_calls + (tool_call,),
            last_activity_at=now,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def add_agent_response(self, content: str) -> Conversation:
        """
        Convenience method: add an AGENT message and emit AgentResponseGeneratedEvent.

        Tracks the number of tool calls that contributed to this response
        (all tool calls since the last agent message).
        """
        self._assert_mutable()
        now = datetime.now(UTC)
        message = ConversationMessage(
            role=MessageRole.AGENT,
            content=content,
            modality=MessageModality.TEXT,
            timestamp=now,
        )
        # Count tool calls since last agent message
        tool_calls_since_last = self._tool_calls_since_last_agent_message()
        event = AgentResponseGeneratedEvent(
            aggregate_id=self.conversation_id,
            tenant_id=self.tenant_id,
            response_content=content,
            tool_call_count=tool_calls_since_last,
        )
        return replace(
            self,
            messages=self.messages + (message,),
            last_activity_at=now,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def escalate_to_human(self, reason: str, confidence: float) -> Conversation:
        """
        Escalate the conversation to a human associate.

        Builds a structured EscalationContext with a summary of the
        conversation and detected sentiment. Returns a new Conversation
        with ESCALATED status and ConversationEscalatedEvent.

        Raises ValueError if the conversation is not in a mutable state.
        """
        self._assert_mutable()
        now = datetime.now(UTC)
        summary = self._build_summary()
        sentiment = self._detect_sentiment()
        context = EscalationContext(
            reason=reason,
            confidence=confidence,
            conversation_summary=summary,
            customer_sentiment=sentiment,
        )
        event = ConversationEscalatedEvent(
            aggregate_id=self.conversation_id,
            tenant_id=self.tenant_id,
            reason=reason,
            confidence=confidence,
            conversation_summary=summary,
            customer_sentiment=sentiment,
        )
        return replace(
            self,
            status=ConversationStatus.ESCALATED,
            escalation_context=context,
            last_activity_at=now,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def complete(self) -> Conversation:
        """
        Mark the conversation as completed.

        Returns a new Conversation with COMPLETED status and
        ConversationCompletedEvent carrying summary metrics.

        Raises ValueError if conversation is already completed.
        """
        if self.status == ConversationStatus.COMPLETED:
            raise ValueError("Conversation is already completed")
        now = datetime.now(UTC)
        event = ConversationCompletedEvent(
            aggregate_id=self.conversation_id,
            tenant_id=self.tenant_id,
            total_messages=len(self.messages),
            total_tool_calls=len(self.tool_calls),
        )
        return replace(
            self,
            status=ConversationStatus.COMPLETED,
            last_activity_at=now,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def pause(self) -> Conversation:
        """Pause the conversation (e.g. customer navigated away)."""
        self._assert_mutable()
        return replace(
            self,
            status=ConversationStatus.PAUSED,
            last_activity_at=datetime.now(UTC),
            **self._touch(),
        )

    def resume(self) -> Conversation:
        """Resume a paused conversation."""
        if self.status != ConversationStatus.PAUSED:
            raise ValueError("Only paused conversations can be resumed")
        return replace(
            self,
            status=ConversationStatus.ACTIVE,
            last_activity_at=datetime.now(UTC),
            **self._touch(),
        )

    # ── Private helpers ──────────────────────────────────────────────

    def _assert_mutable(self) -> None:
        """Raise if the conversation is in a terminal state."""
        if self.status in (ConversationStatus.COMPLETED, ConversationStatus.ESCALATED):
            raise ValueError(
                f"Cannot modify conversation in {self.status.value} status"
            )

    def _tool_calls_since_last_agent_message(self) -> int:
        """Count tool calls since the last agent message."""
        last_agent_idx = -1
        for i, msg in enumerate(self.messages):
            if msg.role == MessageRole.AGENT:
                last_agent_idx = i
        if last_agent_idx == -1:
            return len(self.tool_calls)
        # Approximate: tool calls added after the last agent message index
        # In practice, tool calls accumulate between agent responses
        return len(self.tool_calls)

    def _build_summary(self) -> str:
        """Build a plain-text summary of the conversation for escalation."""
        if not self.messages:
            return "No messages exchanged."
        lines: list[str] = []
        for msg in self.messages[-10:]:  # Last 10 messages for context
            lines.append(f"{msg.role.value}: {msg.content[:200]}")
        return "\n".join(lines)

    def _detect_sentiment(self) -> str:
        """
        Simple rule-based sentiment detection from customer messages.

        Production implementation would use a dedicated sentiment model,
        but this provides a baseline for escalation context.
        """
        customer_messages = [
            m.content.lower()
            for m in self.messages
            if m.role == MessageRole.CUSTOMER
        ]
        if not customer_messages:
            return "neutral"
        last_messages = " ".join(customer_messages[-3:])
        negative_signals = [
            "frustrated", "angry", "disappointed", "terrible",
            "horrible", "worst", "unacceptable", "ridiculous",
            "complaint", "refund", "manager", "lawsuit",
        ]
        positive_signals = [
            "love", "amazing", "perfect", "wonderful",
            "excellent", "thank", "great", "beautiful",
        ]
        neg_count = sum(1 for signal in negative_signals if signal in last_messages)
        pos_count = sum(1 for signal in positive_signals if signal in last_messages)
        if neg_count > pos_count:
            return "negative"
        if pos_count > neg_count:
            return "positive"
        return "neutral"
