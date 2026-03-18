"""Ports (Protocol-based interfaces) for the Agentic CX bounded context."""

from prism.agentic_cx.domain.ports.agent_ports import (
    AgentLLMPort,
    ConversationRepositoryPort,
    CustomerProfilePort,
    ToolExecutionPort,
)
from prism.agentic_cx.domain.ports.channel_ports import (
    ChannelAdapterPort,
    WebChannelPort,
    WhatsAppChannelPort,
)
from prism.agentic_cx.domain.ports.memory_ports import (
    LongTermMemoryPort,
    SessionMemoryPort,
)

__all__ = [
    "AgentLLMPort",
    "ChannelAdapterPort",
    "ConversationRepositoryPort",
    "CustomerProfilePort",
    "LongTermMemoryPort",
    "SessionMemoryPort",
    "ToolExecutionPort",
    "WebChannelPort",
    "WhatsAppChannelPort",
]
