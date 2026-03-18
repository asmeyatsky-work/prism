"""
Agentic CX — Domain Events

Architectural Intent:
- Domain events capture all significant state transitions in conversations
- Events are collected on the Conversation aggregate and dispatched after persistence
- Each event carries tenant_id for multi-tenant Pub/Sub routing
- Events enable cross-context integration: e.g. ConversationCompleted triggers CRM update
- All events extend the shared DomainEvent base (frozen dataclass)

Event Flow:
    ConversationStarted -> MessageReceived -> ToolCallExecuted* ->
    AgentResponseGenerated -> (ConversationEscalated | ConversationCompleted)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prism.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class ConversationStartedEvent(DomainEvent):
    """Emitted when a new conversation is initiated by a customer."""

    customer_id: str = ""
    agent_type: str = ""
    channel: str = ""


@dataclass(frozen=True)
class MessageReceivedEvent(DomainEvent):
    """Emitted when a customer or agent message is added to the conversation."""

    role: str = ""
    content: str = ""
    modality: str = "TEXT"


@dataclass(frozen=True)
class ToolCallExecutedEvent(DomainEvent):
    """
    Emitted after each agent tool invocation completes.

    Captures tool name, arguments, result, and latency for
    observability dashboards and performance monitoring.
    """

    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    success: bool = True


@dataclass(frozen=True)
class AgentResponseGeneratedEvent(DomainEvent):
    """
    Emitted when the agent produces a response for the customer.

    Tracks the response content and the number of tool calls
    that contributed to generating this response.
    """

    response_content: str = ""
    tool_call_count: int = 0


@dataclass(frozen=True)
class ConversationEscalatedEvent(DomainEvent):
    """
    Emitted when a conversation is escalated to a human associate.

    Carries structured escalation context including the reason,
    confidence level at escalation point, and customer sentiment.
    """

    reason: str = ""
    confidence: float = 0.0
    conversation_summary: str = ""
    customer_sentiment: str = "neutral"


@dataclass(frozen=True)
class ConversationCompletedEvent(DomainEvent):
    """
    Emitted when a conversation is closed by the agent or customer.

    The total_messages and total_tool_calls fields provide summary
    metrics for analytics without requiring event replay.
    """

    total_messages: int = 0
    total_tool_calls: int = 0
