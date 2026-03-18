"""
Agentic CX — Message Value Objects

Architectural Intent:
- Immutable value objects representing conversation messages, tool calls, and escalation context
- ConversationMessage captures multi-modal interactions (text, image, voice)
- AgentToolCall records every tool invocation for audit and replay
- EscalationContext carries structured handoff data to human associates
- All are frozen dataclasses per skill2026 Rule 3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from prism.shared.domain.value_objects import ValueObject


class MessageRole(str, Enum):
    """Who sent the message in a conversation turn."""

    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class MessageModality(str, Enum):
    """Content modality of a conversation message."""

    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VOICE = "VOICE"


@dataclass(frozen=True)
class ConversationMessage(ValueObject):
    """
    A single message within a conversation.

    Supports multi-modal content: text messages, image attachments
    (e.g. customer photo for virtual try-on), and voice transcriptions.
    Metadata carries channel-specific payload (e.g. WhatsApp message ID).
    """

    role: MessageRole
    content: str
    modality: MessageModality = MessageModality.TEXT
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content and self.modality == MessageModality.TEXT:
            raise ValueError("Text messages must have non-empty content")


@dataclass(frozen=True)
class AgentToolCall(ValueObject):
    """
    Record of a single tool invocation by the agent.

    Every tool call is logged with its arguments, result, duration,
    and success status for observability and replay capability.
    Duration is tracked in milliseconds for latency monitoring.
    """

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    success: bool = True

    def __post_init__(self) -> None:
        if not self.tool_name:
            raise ValueError("Tool name must be non-empty")
        if self.duration_ms < 0:
            raise ValueError("Duration cannot be negative")


@dataclass(frozen=True)
class EscalationContext(ValueObject):
    """
    Structured context for human escalation handoff.

    Carries the reason for escalation, the agent's confidence level
    at the point of escalation, a summary of the conversation so far,
    and the detected customer sentiment to help the human associate
    continue seamlessly.
    """

    reason: str
    confidence: float
    conversation_summary: str = ""
    customer_sentiment: str = "neutral"

    def __post_init__(self) -> None:
        if not self.reason:
            raise ValueError("Escalation reason must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
