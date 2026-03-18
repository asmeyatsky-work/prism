"""
Agentic CX — Application DTOs

Architectural Intent:
- Pydantic models for structured data transfer across layer boundaries
- DTOs decouple presentation/API layer from domain entities
- All DTOs are serialisable for MCP tool responses and API payloads
- ConversationDTO and MessageDTO are the primary response shapes
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MessageDTO(BaseModel):
    """Data transfer object for a single conversation message."""

    role: str
    content: str
    modality: str = "TEXT"
    timestamp: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentToolCallDTO(BaseModel):
    """Data transfer object for a tool invocation record."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0
    success: bool = True


class ConversationDTO(BaseModel):
    """Data transfer object for a full conversation state."""

    conversation_id: str
    tenant_id: str
    customer_id: str = ""
    agent_type: str
    channel: str
    status: str
    messages: list[MessageDTO] = Field(default_factory=list)
    tool_calls: list[AgentToolCallDTO] = Field(default_factory=list)
    started_at: datetime | None = None
    last_activity_at: datetime | None = None


class CustomerProfileDTO(BaseModel):
    """Data transfer object for customer profile context."""

    customer_id: str
    tenant_id: str
    preferences: dict[str, Any] = Field(default_factory=dict)
    style_tags: list[str] = Field(default_factory=list)
    purchase_history_ids: list[str] = Field(default_factory=list)
    wishlist_ids: list[str] = Field(default_factory=list)
    size_profile: dict[str, Any] = Field(default_factory=dict)
    preferred_locale: str = "en"
    conversation_count: int = 0
    is_new_customer: bool = True


class EscalationDTO(BaseModel):
    """Data transfer object for escalation context."""

    conversation_id: str
    reason: str
    confidence: float
    conversation_summary: str = ""
    customer_sentiment: str = "neutral"
    agent_type: str = ""
    channel: str = ""


class AgentResponseDTO(BaseModel):
    """Data transfer object for an agent response to a customer message."""

    conversation_id: str
    response_content: str
    tool_calls_made: list[AgentToolCallDTO] = Field(default_factory=list)
    should_escalate: bool = False
    escalation: EscalationDTO | None = None


class StartConversationRequestDTO(BaseModel):
    """Request DTO for starting a new conversation."""

    tenant_id: str
    agent_type: str = "PERSONAL_STYLIST"
    channel: str = "WEB"
    customer_id: str = ""
    initial_message: str = ""


class SendMessageRequestDTO(BaseModel):
    """Request DTO for sending a customer message."""

    conversation_id: str
    content: str
    modality: str = "TEXT"
    metadata: dict[str, Any] = Field(default_factory=dict)
