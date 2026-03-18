"""
Tests — Conversation Domain Service

Tests for stateless domain service logic:
- Escalation decision logic
- Agent context building
- Intent-based tool selection
"""

from __future__ import annotations

import pytest

from prism.agentic_cx.domain.entities.agent_persona import AgentPersona, PersonaTone
from prism.agentic_cx.domain.entities.conversation import (
    AgentType,
    Conversation,
)
from prism.agentic_cx.domain.entities.customer_profile import CustomerProfile
from prism.agentic_cx.domain.services.conversation_service import ConversationService
from prism.agentic_cx.domain.value_objects.agent_config import AgentToolkit, Channel
from prism.agentic_cx.domain.value_objects.messages import MessageRole
from prism.shared.domain.value_objects import Locale


@pytest.fixture
def service() -> ConversationService:
    return ConversationService()


@pytest.fixture
def persona() -> AgentPersona:
    return AgentPersona(
        tenant_id="gucci",
        agent_type=AgentType.PERSONAL_STYLIST,
        brand_name="Gucci",
        persona_name="Sofia",
        tone=PersonaTone.LUXURY,
        escalation_threshold=0.3,
    )


@pytest.fixture
def toolkit() -> AgentToolkit:
    return AgentToolkit(
        available_tools=(
            "catalogue_search",
            "virtual_tryon",
            "inventory_check",
            "wishlist_manage",
            "appointment_book",
            "associate_escalate",
        )
    )


@pytest.fixture
def conversation() -> Conversation:
    return Conversation.start(
        tenant_id="gucci",
        agent_type=AgentType.PERSONAL_STYLIST,
        channel=Channel.WEB,
        customer_id="cust_001",
    )


@pytest.fixture
def customer_profile() -> CustomerProfile:
    return CustomerProfile(
        customer_id="cust_001",
        tenant_id="gucci",
        preferences={"colors": ["black", "burgundy"]},
        style_tags=("classic", "minimalist"),
        purchase_history_ids=("ord_001", "ord_002"),
        preferred_locale=Locale(language="en", region="US"),
        conversation_count=3,
    )


class TestShouldEscalate:
    """Tests for escalation decision logic."""

    def test_escalates_when_confidence_below_threshold(
        self, service: ConversationService, conversation: Conversation, persona: AgentPersona
    ) -> None:
        assert service.should_escalate(conversation, persona, current_confidence=0.1) is True

    def test_does_not_escalate_when_confidence_above_threshold(
        self, service: ConversationService, conversation: Conversation, persona: AgentPersona
    ) -> None:
        assert service.should_escalate(conversation, persona, current_confidence=0.8) is False

    def test_escalates_on_explicit_human_request(
        self, service: ConversationService, persona: AgentPersona
    ) -> None:
        conv = Conversation.start("gucci", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(
            MessageRole.CUSTOMER, "I want to speak to a real person"
        )
        assert service.should_escalate(conv, persona, current_confidence=0.9) is True

    def test_escalates_on_manager_request(
        self, service: ConversationService, persona: AgentPersona
    ) -> None:
        conv = Conversation.start("gucci", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(
            MessageRole.CUSTOMER, "Let me talk to your manager"
        )
        assert service.should_escalate(conv, persona, current_confidence=0.9) is True

    def test_escalates_on_consecutive_tool_failures(
        self, service: ConversationService, persona: AgentPersona
    ) -> None:
        conv = Conversation.start("gucci", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_tool_call("tool1", {}, {"error": "fail"}, success=False)
        conv = conv.add_tool_call("tool2", {}, {"error": "fail"}, success=False)
        conv = conv.add_tool_call("tool3", {}, {"error": "fail"}, success=False)
        assert service.should_escalate(conv, persona, current_confidence=0.9) is True

    def test_does_not_escalate_on_mixed_tool_results(
        self, service: ConversationService, persona: AgentPersona
    ) -> None:
        conv = Conversation.start("gucci", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_tool_call("tool1", {}, {}, success=True)
        conv = conv.add_tool_call("tool2", {}, {"error": "fail"}, success=False)
        conv = conv.add_tool_call("tool3", {}, {}, success=True)
        assert service.should_escalate(conv, persona, current_confidence=0.9) is False


class TestBuildAgentContext:
    """Tests for LLM context assembly."""

    def test_context_contains_conversation_history(
        self,
        service: ConversationService,
        conversation: Conversation,
    ) -> None:
        conv = conversation.add_message(MessageRole.CUSTOMER, "Show me bags")
        context = service.build_agent_context(conv, customer_profile=None)
        assert len(context["messages"]) == 1
        assert context["messages"][0]["content"] == "Show me bags"

    def test_context_contains_customer_profile(
        self,
        service: ConversationService,
        conversation: Conversation,
        customer_profile: CustomerProfile,
    ) -> None:
        context = service.build_agent_context(conversation, customer_profile)
        assert "customer" in context
        assert context["customer"]["customer_id"] == "cust_001"
        assert context["customer"]["is_returning"] is True
        assert "classic" in context["customer"]["style_tags"]

    def test_context_contains_system_prompt(
        self,
        service: ConversationService,
        conversation: Conversation,
        persona: AgentPersona,
    ) -> None:
        context = service.build_agent_context(
            conversation, customer_profile=None, persona=persona
        )
        assert "system_prompt" in context
        assert "Sofia" in context["system_prompt"]
        assert "Gucci" in context["system_prompt"]

    def test_context_for_new_customer(
        self,
        service: ConversationService,
        conversation: Conversation,
        persona: AgentPersona,
    ) -> None:
        new_profile = CustomerProfile(
            customer_id="cust_new",
            tenant_id="gucci",
            conversation_count=0,
        )
        context = service.build_agent_context(
            conversation, new_profile, persona=persona
        )
        assert "new customer" in context["system_prompt"].lower()

    def test_context_includes_session_memory(
        self,
        service: ConversationService,
        conversation: Conversation,
    ) -> None:
        session = {"discussed_products": ["prod_001"], "budget": "$2000-$3000"}
        context = service.build_agent_context(
            conversation, customer_profile=None, session_context=session
        )
        assert context["session"] == session

    def test_context_includes_tool_history(
        self,
        service: ConversationService,
    ) -> None:
        conv = Conversation.start("gucci", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_tool_call(
            "catalogue_search",
            {"query": "bag"},
            {"products": [{"id": "p1"}]},
        )
        context = service.build_agent_context(conv, customer_profile=None)
        assert len(context["tool_history"]) == 1
        assert context["tool_history"][0]["tool"] == "catalogue_search"


class TestSelectToolsForIntent:
    """Tests for intent-based tool selection."""

    def test_search_intent_selects_catalogue(
        self, service: ConversationService, toolkit: AgentToolkit
    ) -> None:
        tools = service.select_tools_for_intent("Show me leather bags", toolkit)
        assert "catalogue_search" in tools

    def test_tryon_intent_selects_virtual_tryon(
        self, service: ConversationService, toolkit: AgentToolkit
    ) -> None:
        tools = service.select_tools_for_intent(
            "Can I try it on virtually?", toolkit
        )
        assert "virtual_tryon" in tools

    def test_stock_intent_selects_inventory(
        self, service: ConversationService, toolkit: AgentToolkit
    ) -> None:
        tools = service.select_tools_for_intent(
            "Is this in stock?", toolkit
        )
        assert "inventory_check" in tools

    def test_appointment_intent(
        self, service: ConversationService, toolkit: AgentToolkit
    ) -> None:
        tools = service.select_tools_for_intent(
            "I'd like to book an appointment", toolkit
        )
        assert "appointment_book" in tools

    def test_wishlist_intent(
        self, service: ConversationService, toolkit: AgentToolkit
    ) -> None:
        tools = service.select_tools_for_intent(
            "Save this to my wishlist", toolkit
        )
        assert "wishlist_manage" in tools

    def test_escalation_intent(
        self, service: ConversationService, toolkit: AgentToolkit
    ) -> None:
        tools = service.select_tools_for_intent(
            "I'd like to speak to a human representative", toolkit
        )
        assert "associate_escalate" in tools

    def test_no_specific_intent_returns_all_tools(
        self, service: ConversationService, toolkit: AgentToolkit
    ) -> None:
        tools = service.select_tools_for_intent(
            "What do you suggest?", toolkit
        )
        assert len(tools) == len(toolkit.available_tools)

    def test_unavailable_tool_filtered_out(
        self, service: ConversationService
    ) -> None:
        limited_toolkit = AgentToolkit(
            available_tools=("catalogue_search",)
        )
        tools = service.select_tools_for_intent(
            "Can I try it on?", limited_toolkit
        )
        assert "virtual_tryon" not in tools

    def test_multiple_intents_select_multiple_tools(
        self, service: ConversationService, toolkit: AgentToolkit
    ) -> None:
        tools = service.select_tools_for_intent(
            "Is this available in stock? Can I try it on?", toolkit
        )
        assert "inventory_check" in tools
        assert "virtual_tryon" in tools
