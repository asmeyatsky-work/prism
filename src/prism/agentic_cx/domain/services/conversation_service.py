"""
Agentic CX — Conversation Domain Service

Architectural Intent:
- Domain service encapsulating logic that spans multiple entities
- should_escalate: evaluates whether the agent should hand off to a human
- build_agent_context: assembles the full LLM context from conversation + profile + memory
- select_tools_for_intent: determines which tools are relevant to the customer's message
- Stateless service — all state comes from entity parameters
"""

from __future__ import annotations

import re
from typing import Any

from prism.agentic_cx.domain.entities.agent_persona import AgentPersona
from prism.agentic_cx.domain.entities.conversation import Conversation
from prism.agentic_cx.domain.entities.customer_profile import CustomerProfile
from prism.agentic_cx.domain.value_objects.agent_config import AgentToolkit
from prism.agentic_cx.domain.value_objects.messages import MessageRole


class ConversationService:
    """
    Stateless domain service for conversation-level logic.

    Encapsulates business rules that span the Conversation aggregate,
    AgentPersona, and CustomerProfile entities. All methods are pure
    functions operating on their parameters.
    """

    @staticmethod
    def should_escalate(
        conversation: Conversation,
        persona: AgentPersona,
        current_confidence: float = 1.0,
    ) -> bool:
        """
        Determine whether the conversation should be escalated to a human.

        Escalation triggers:
        1. Agent confidence drops below persona's escalation threshold
        2. Customer explicitly requests a human
        3. Multiple consecutive tool failures
        4. Negative customer sentiment detected

        Args:
            conversation: The current conversation state.
            persona: The agent persona with escalation threshold.
            current_confidence: The agent's confidence in its last response.

        Returns:
            True if escalation is recommended.
        """
        # Check confidence threshold
        if current_confidence < persona.escalation_threshold:
            return True

        # Check for explicit human request in recent customer messages
        recent_customer_messages = [
            m.content.lower()
            for m in conversation.messages[-5:]
            if m.role == MessageRole.CUSTOMER
        ]
        human_request_patterns = [
            r"\bhuman\b", r"\bperson\b", r"\bagent\b", r"\bmanager\b",
            r"\bsupervisor\b", r"\breal person\b", r"\bspeak to someone\b",
            r"\btalk to someone\b", r"\brepresentative\b",
        ]
        for message in recent_customer_messages:
            for pattern in human_request_patterns:
                if re.search(pattern, message):
                    return True

        # Check for consecutive tool failures
        if len(conversation.tool_calls) >= 3:
            recent_calls = conversation.tool_calls[-3:]
            if all(not tc.success for tc in recent_calls):
                return True

        # Check for negative sentiment buildup
        sentiment = conversation._detect_sentiment()
        if sentiment == "negative" and len(conversation.messages) > 4:
            return True

        return False

    @staticmethod
    def build_agent_context(
        conversation: Conversation,
        customer_profile: CustomerProfile | None,
        session_context: dict[str, Any] | None = None,
        persona: AgentPersona | None = None,
    ) -> dict[str, Any]:
        """
        Assemble the full LLM context for a conversation turn.

        Combines:
        - Conversation history (messages)
        - Customer profile (ContextOps data)
        - Session memory (working context from current conversation)
        - Agent persona system prompt

        This is the primary context payload passed to AgentLLMPort.generate_response().
        """
        # Build message history for LLM
        messages: list[dict[str, Any]] = []
        for msg in conversation.messages:
            messages.append({
                "role": msg.role.value.lower(),
                "content": msg.content,
                "modality": msg.modality.value,
            })

        # Build tool call history
        tool_history: list[dict[str, Any]] = []
        for tc in conversation.tool_calls:
            tool_history.append({
                "tool": tc.tool_name,
                "arguments": tc.arguments,
                "result": tc.result,
                "success": tc.success,
            })

        context: dict[str, Any] = {
            "conversation_id": conversation.conversation_id,
            "tenant_id": conversation.tenant_id,
            "channel": conversation.channel.value,
            "agent_type": conversation.agent_type.value,
            "messages": messages,
            "tool_history": tool_history,
            "message_count": len(conversation.messages),
        }

        # Inject customer profile (ContextOps)
        if customer_profile:
            context["customer"] = customer_profile.to_agent_context()

        # Inject session memory
        if session_context:
            context["session"] = session_context

        # Inject system prompt from persona
        if persona:
            additional_context = ""
            if customer_profile:
                if customer_profile.is_new_customer():
                    additional_context = "This is a new customer. Be welcoming and exploratory."
                else:
                    additional_context = (
                        f"Returning customer with {customer_profile.conversation_count} "
                        f"previous conversations. Reference their history when relevant."
                    )
            context["system_prompt"] = persona.build_system_prompt(additional_context)

        return context

    @staticmethod
    def select_tools_for_intent(
        message: str,
        available_tools: AgentToolkit,
    ) -> list[str]:
        """
        Select relevant tools based on customer message intent.

        Performs keyword-based intent detection to narrow the tool set
        presented to the LLM, reducing cognitive load and improving
        response accuracy. Production implementations may use a
        dedicated intent classifier.

        Args:
            message: The customer's message text.
            available_tools: The full set of tools available to the agent.

        Returns:
            Filtered list of tool names relevant to the detected intent.
        """
        msg_lower = message.lower()

        # Intent-to-tool mapping
        intent_tool_map: dict[str, list[str]] = {
            "search": ["catalogue_search"],
            "find": ["catalogue_search"],
            "looking for": ["catalogue_search"],
            "show me": ["catalogue_search"],
            "browse": ["catalogue_search"],
            "recommend": ["catalogue_search"],
            "try on": ["virtual_tryon"],
            "try it on": ["virtual_tryon"],
            "how would it look": ["virtual_tryon"],
            "visuali": ["virtual_tryon"],
            "in stock": ["inventory_check"],
            "available": ["inventory_check"],
            "inventory": ["inventory_check"],
            "stock": ["inventory_check"],
            "wishlist": ["wishlist_manage"],
            "save for later": ["wishlist_manage"],
            "favorites": ["wishlist_manage"],
            "appointment": ["appointment_book"],
            "book": ["appointment_book"],
            "visit": ["appointment_book"],
            "schedule": ["appointment_book"],
            "store visit": ["appointment_book"],
            "speak to": ["associate_escalate"],
            "human": ["associate_escalate"],
            "representative": ["associate_escalate"],
            "order": ["order_status"],
            "tracking": ["order_status"],
            "where is my": ["order_status"],
            "delivery": ["order_status"],
            "return": ["returns"],
            "exchange": ["returns"],
            "refund": ["returns"],
            "gift": ["gift_wrapping"],
            "wrap": ["gift_wrapping"],
        }

        selected: set[str] = set()
        for keyword, tools in intent_tool_map.items():
            if keyword in msg_lower:
                for tool in tools:
                    if available_tools.has_tool(tool):
                        selected.add(tool)

        # If no specific intent detected, return all available tools
        # so the LLM can decide
        if not selected:
            return list(available_tools.available_tools)

        return sorted(selected)
