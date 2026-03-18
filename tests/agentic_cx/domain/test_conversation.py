"""
Tests — Conversation Aggregate Root

Pure domain tests verifying:
- Conversation lifecycle: start -> message -> tool call -> complete
- Immutability: every mutation returns a new instance
- Domain events: correct events emitted for each state transition
- Invariants: terminal states reject modifications
- Escalation: builds context with summary and sentiment
"""

from __future__ import annotations

import pytest

from prism.agentic_cx.domain.entities.conversation import (
    AgentType,
    Conversation,
    ConversationStatus,
)
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
    MessageModality,
    MessageRole,
)


class TestConversationStart:
    """Tests for conversation creation."""

    def test_start_creates_conversation_with_correct_fields(self) -> None:
        conv = Conversation.start(
            tenant_id="gucci",
            agent_type=AgentType.PERSONAL_STYLIST,
            channel=Channel.WEB,
            customer_id="cust_001",
        )
        assert conv.tenant_id == "gucci"
        assert conv.agent_type == AgentType.PERSONAL_STYLIST
        assert conv.channel == Channel.WEB
        assert conv.customer_id == "cust_001"
        assert conv.status == ConversationStatus.ACTIVE
        assert len(conv.messages) == 0
        assert len(conv.tool_calls) == 0

    def test_start_emits_conversation_started_event(self) -> None:
        conv = Conversation.start(
            tenant_id="burberry",
            agent_type=AgentType.COMMERCE_CONCIERGE,
            channel=Channel.WHATSAPP,
        )
        assert len(conv.domain_events) == 1
        event = conv.domain_events[0]
        assert isinstance(event, ConversationStartedEvent)
        assert event.tenant_id == "burberry"
        assert event.agent_type == "COMMERCE_CONCIERGE"
        assert event.channel == "WHATSAPP"

    def test_start_generates_unique_conversation_id(self) -> None:
        conv1 = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv2 = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        assert conv1.conversation_id != conv2.conversation_id

    def test_start_without_customer_id(self) -> None:
        conv = Conversation.start(
            tenant_id="gucci",
            agent_type=AgentType.PERSONAL_STYLIST,
            channel=Channel.WEB,
        )
        assert conv.customer_id == ""


class TestConversationMessages:
    """Tests for message handling."""

    def test_add_message_returns_new_instance(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        updated = conv.add_message(MessageRole.CUSTOMER, "Hello!")
        assert updated is not conv
        assert len(updated.messages) == 1
        assert len(conv.messages) == 0  # Original unchanged

    def test_add_message_preserves_content(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        updated = conv.add_message(
            MessageRole.CUSTOMER, "I'm looking for a handbag"
        )
        msg = updated.messages[0]
        assert msg.role == MessageRole.CUSTOMER
        assert msg.content == "I'm looking for a handbag"
        assert msg.modality == MessageModality.TEXT

    def test_add_message_emits_event(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        updated = conv.add_message(MessageRole.CUSTOMER, "Hello!")
        events = [e for e in updated.domain_events if isinstance(e, MessageReceivedEvent)]
        assert len(events) == 1
        assert events[0].role == "CUSTOMER"
        assert events[0].content == "Hello!"

    def test_add_agent_response_emits_response_event(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "Hello!")
        updated = conv.add_agent_response("Welcome to Gucci!")
        events = [
            e for e in updated.domain_events
            if isinstance(e, AgentResponseGeneratedEvent)
        ]
        assert len(events) == 1
        assert events[0].response_content == "Welcome to Gucci!"

    def test_multiple_messages_accumulate(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "Hello!")
        conv = conv.add_agent_response("Welcome!")
        conv = conv.add_message(MessageRole.CUSTOMER, "Show me bags")
        assert len(conv.messages) == 3

    def test_add_image_message(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        updated = conv.add_message(
            MessageRole.CUSTOMER,
            "https://example.com/photo.jpg",
            modality=MessageModality.IMAGE,
        )
        assert updated.messages[0].modality == MessageModality.IMAGE


class TestConversationToolCalls:
    """Tests for tool call recording."""

    def test_add_tool_call_returns_new_instance(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        updated = conv.add_tool_call(
            tool_name="catalogue_search",
            arguments={"query": "leather bag"},
            result={"products": []},
            duration_ms=150,
        )
        assert updated is not conv
        assert len(updated.tool_calls) == 1
        assert len(conv.tool_calls) == 0

    def test_add_tool_call_records_details(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        updated = conv.add_tool_call(
            tool_name="inventory_check",
            arguments={"product_id": "prod_001"},
            result={"available": True, "stock": 5},
            duration_ms=80,
            success=True,
        )
        tc = updated.tool_calls[0]
        assert tc.tool_name == "inventory_check"
        assert tc.arguments == {"product_id": "prod_001"}
        assert tc.result["available"] is True
        assert tc.duration_ms == 80
        assert tc.success is True

    def test_add_tool_call_emits_event(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        updated = conv.add_tool_call(
            tool_name="virtual_tryon",
            arguments={"product_id": "prod_001"},
            result={"tryon_url": "https://tryon.example/123"},
            duration_ms=500,
        )
        events = [
            e for e in updated.domain_events
            if isinstance(e, ToolCallExecutedEvent)
        ]
        assert len(events) == 1
        assert events[0].tool_name == "virtual_tryon"
        assert events[0].duration_ms == 500

    def test_failed_tool_call(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        updated = conv.add_tool_call(
            tool_name="inventory_check",
            arguments={"product_id": "missing"},
            result={"error": "Product not found"},
            duration_ms=50,
            success=False,
        )
        assert updated.tool_calls[0].success is False


class TestConversationEscalation:
    """Tests for escalation to human associate."""

    def test_escalate_changes_status(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "I want to speak to a manager")
        escalated = conv.escalate_to_human(reason="Customer request", confidence=0.2)
        assert escalated.status == ConversationStatus.ESCALATED

    def test_escalate_builds_context(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "This is frustrating!")
        escalated = conv.escalate_to_human(reason="Negative sentiment", confidence=0.15)
        ctx = escalated.escalation_context
        assert ctx is not None
        assert ctx.reason == "Negative sentiment"
        assert ctx.confidence == 0.15
        assert "frustrating" in ctx.conversation_summary.lower()

    def test_escalate_emits_event(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        escalated = conv.escalate_to_human(reason="Low confidence", confidence=0.1)
        events = [
            e for e in escalated.domain_events
            if isinstance(e, ConversationEscalatedEvent)
        ]
        assert len(events) == 1
        assert events[0].reason == "Low confidence"

    def test_escalated_conversation_rejects_messages(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        escalated = conv.escalate_to_human(reason="Test", confidence=0.1)
        with pytest.raises(ValueError, match="ESCALATED"):
            escalated.add_message(MessageRole.CUSTOMER, "Hello?")


class TestConversationCompletion:
    """Tests for conversation completion."""

    def test_complete_changes_status(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "Thank you!")
        completed = conv.complete()
        assert completed.status == ConversationStatus.COMPLETED

    def test_complete_emits_event_with_metrics(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "Hello")
        conv = conv.add_agent_response("Welcome!")
        conv = conv.add_tool_call("catalogue_search", {}, {})
        completed = conv.complete()
        events = [
            e for e in completed.domain_events
            if isinstance(e, ConversationCompletedEvent)
        ]
        assert len(events) == 1
        assert events[0].total_messages == 2
        assert events[0].total_tool_calls == 1

    def test_completed_conversation_rejects_messages(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        completed = conv.complete()
        with pytest.raises(ValueError, match="COMPLETED"):
            completed.add_message(MessageRole.CUSTOMER, "Hello?")

    def test_double_complete_raises(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        completed = conv.complete()
        with pytest.raises(ValueError, match="already completed"):
            completed.complete()


class TestConversationPauseResume:
    """Tests for pause/resume lifecycle."""

    def test_pause_changes_status(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        paused = conv.pause()
        assert paused.status == ConversationStatus.PAUSED

    def test_resume_returns_to_active(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        paused = conv.pause()
        resumed = paused.resume()
        assert resumed.status == ConversationStatus.ACTIVE

    def test_resume_non_paused_raises(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        with pytest.raises(ValueError, match="paused"):
            conv.resume()


class TestConversationSentiment:
    """Tests for sentiment detection."""

    def test_negative_sentiment_detected(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "This is terrible and unacceptable!")
        assert conv._detect_sentiment() == "negative"

    def test_positive_sentiment_detected(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "This is amazing and wonderful!")
        assert conv._detect_sentiment() == "positive"

    def test_neutral_sentiment_default(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "Can you check if this is available?")
        assert conv._detect_sentiment() == "neutral"


class TestConversationClearEvents:
    """Tests for event management."""

    def test_clear_events_removes_all_events(self) -> None:
        conv = Conversation.start("t1", AgentType.PERSONAL_STYLIST, Channel.WEB)
        conv = conv.add_message(MessageRole.CUSTOMER, "Hello")
        assert len(conv.domain_events) > 0
        cleared = conv.clear_events()
        assert len(cleared.domain_events) == 0
        # Messages preserved
        assert len(cleared.messages) == 1
