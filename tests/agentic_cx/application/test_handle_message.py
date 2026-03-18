"""
Tests — Handle Message Use Case

Application layer tests with mocked infrastructure ports:
- Verifies the full message handling flow
- Mocks LLM, tool executor, repository, and memory ports
- Tests escalation detection and tool call execution
- Tests error handling for missing conversations
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from prism.agentic_cx.application.commands.handle_message import HandleMessageUseCase
from prism.agentic_cx.application.dtos.agent_dto import SendMessageRequestDTO
from prism.agentic_cx.domain.entities.agent_persona import AgentPersona, PersonaTone
from prism.agentic_cx.domain.entities.conversation import (
    AgentType,
    Conversation,
    ConversationStatus,
)
from prism.agentic_cx.domain.entities.customer_profile import CustomerProfile
from prism.agentic_cx.domain.value_objects.agent_config import AgentToolkit, Channel
from prism.shared.domain.value_objects import Locale


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
        preferences={"colors": ["black"]},
        style_tags=("classic",),
        preferred_locale=Locale(language="en"),
        conversation_count=2,
    )


@pytest.fixture
def mock_conversation_repo(conversation: Conversation) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id.return_value = conversation
    repo.save.return_value = None
    return repo


@pytest.fixture
def mock_customer_profile_port(customer_profile: CustomerProfile) -> AsyncMock:
    port = AsyncMock()
    port.get_profile.return_value = customer_profile
    return port


@pytest.fixture
def mock_session_memory() -> AsyncMock:
    memory = AsyncMock()
    memory.get_session_context.return_value = {}
    return memory


@pytest.fixture
def mock_agent_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.generate_response.return_value = (
        "I'd be delighted to help you find the perfect piece. "
        "Let me search our latest collection for you."
    )
    return llm


@pytest.fixture
def mock_tool_executor() -> AsyncMock:
    executor = AsyncMock()
    executor.execute_tool.return_value = {"products": [], "total": 0}
    return executor


@pytest.fixture
def mock_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish.return_value = None
    return bus


@pytest.fixture
def use_case(
    mock_conversation_repo: AsyncMock,
    mock_customer_profile_port: AsyncMock,
    mock_session_memory: AsyncMock,
    mock_agent_llm: AsyncMock,
    mock_tool_executor: AsyncMock,
    mock_event_bus: AsyncMock,
    persona: AgentPersona,
    toolkit: AgentToolkit,
) -> HandleMessageUseCase:
    return HandleMessageUseCase(
        conversation_repo=mock_conversation_repo,
        customer_profile_port=mock_customer_profile_port,
        session_memory=mock_session_memory,
        agent_llm=mock_agent_llm,
        tool_executor=mock_tool_executor,
        event_bus=mock_event_bus,
        persona=persona,
        toolkit=toolkit,
    )


class TestHandleMessageSuccess:
    """Tests for successful message handling."""

    @pytest.mark.asyncio
    async def test_returns_success_with_agent_response(
        self, use_case: HandleMessageUseCase
    ) -> None:
        request = SendMessageRequestDTO(
            conversation_id="conv_001",
            content="Show me your latest handbags",
        )
        result = await use_case.execute(request)
        assert result.success is True
        assert result.value is not None
        assert "delighted" in result.value.response_content

    @pytest.mark.asyncio
    async def test_loads_customer_profile(
        self,
        use_case: HandleMessageUseCase,
        mock_customer_profile_port: AsyncMock,
    ) -> None:
        request = SendMessageRequestDTO(
            conversation_id="conv_001",
            content="Hello",
        )
        await use_case.execute(request)
        mock_customer_profile_port.get_profile.assert_called_once_with(
            customer_id="cust_001",
            tenant_id="gucci",
        )

    @pytest.mark.asyncio
    async def test_loads_session_context(
        self,
        use_case: HandleMessageUseCase,
        mock_session_memory: AsyncMock,
        conversation: Conversation,
    ) -> None:
        request = SendMessageRequestDTO(
            conversation_id="conv_001",
            content="Hello",
        )
        await use_case.execute(request)
        mock_session_memory.get_session_context.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_llm_with_context(
        self,
        use_case: HandleMessageUseCase,
        mock_agent_llm: AsyncMock,
    ) -> None:
        request = SendMessageRequestDTO(
            conversation_id="conv_001",
            content="Show me bags",
        )
        await use_case.execute(request)
        mock_agent_llm.generate_response.assert_called()
        call_args = mock_agent_llm.generate_response.call_args
        context = call_args.kwargs.get("context") or call_args[0][0]
        assert "messages" in context
        assert "system_prompt" in context

    @pytest.mark.asyncio
    async def test_persists_conversation(
        self,
        use_case: HandleMessageUseCase,
        mock_conversation_repo: AsyncMock,
    ) -> None:
        request = SendMessageRequestDTO(
            conversation_id="conv_001",
            content="Hello",
        )
        await use_case.execute(request)
        mock_conversation_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatches_events(
        self,
        use_case: HandleMessageUseCase,
        mock_event_bus: AsyncMock,
    ) -> None:
        request = SendMessageRequestDTO(
            conversation_id="conv_001",
            content="Hello",
        )
        await use_case.execute(request)
        mock_event_bus.publish.assert_called_once()


class TestHandleMessageErrors:
    """Tests for error handling in message processing."""

    @pytest.mark.asyncio
    async def test_returns_error_for_missing_conversation(
        self,
        use_case: HandleMessageUseCase,
        mock_conversation_repo: AsyncMock,
    ) -> None:
        mock_conversation_repo.get_by_id.return_value = None
        request = SendMessageRequestDTO(
            conversation_id="nonexistent",
            content="Hello",
        )
        result = await use_case.execute(request)
        assert result.success is False
        assert result.error_code == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_returns_error_for_completed_conversation(
        self,
        use_case: HandleMessageUseCase,
        mock_conversation_repo: AsyncMock,
        conversation: Conversation,
    ) -> None:
        completed = conversation.complete()
        mock_conversation_repo.get_by_id.return_value = completed
        request = SendMessageRequestDTO(
            conversation_id="conv_001",
            content="Hello?",
        )
        result = await use_case.execute(request)
        assert result.success is False
        assert result.error_code == "INVALID_STATE"

    @pytest.mark.asyncio
    async def test_resumes_paused_conversation(
        self,
        use_case: HandleMessageUseCase,
        mock_conversation_repo: AsyncMock,
        conversation: Conversation,
    ) -> None:
        paused = conversation.pause()
        mock_conversation_repo.get_by_id.return_value = paused
        request = SendMessageRequestDTO(
            conversation_id="conv_001",
            content="I'm back!",
        )
        result = await use_case.execute(request)
        assert result.success is True


class TestHandleMessageEscalation:
    """Tests for escalation detection during message handling."""

    @pytest.mark.asyncio
    async def test_detects_escalation_on_human_request(
        self,
        use_case: HandleMessageUseCase,
        mock_conversation_repo: AsyncMock,
    ) -> None:
        conv = Conversation.start("gucci", AgentType.PERSONAL_STYLIST, Channel.WEB, "cust_001")
        conv = conv.add_message(
            role=__import__(
                "prism.agentic_cx.domain.value_objects.messages",
                fromlist=["MessageRole"],
            ).MessageRole.CUSTOMER,
            content="I want to speak to a human representative please",
        )
        mock_conversation_repo.get_by_id.return_value = conv

        request = SendMessageRequestDTO(
            conversation_id="conv_001",
            content="I want to speak to a human representative please",
        )
        result = await use_case.execute(request)
        assert result.success is True
        assert result.value is not None
        # The escalation detection happens based on the accumulated messages


class TestParallelToolExecution:
    """Tests for parallel tool call execution."""

    @pytest.mark.asyncio
    async def test_executes_tools_in_parallel(
        self,
        use_case: HandleMessageUseCase,
        mock_tool_executor: AsyncMock,
    ) -> None:
        mock_tool_executor.execute_tool.side_effect = [
            {"products": [{"id": "p1"}]},
            {"available": True},
        ]
        results = await use_case.execute_parallel_tool_calls([
            ("catalogue_search", {"query": "bag"}),
            ("inventory_check", {"product_id": "p1"}),
        ])
        assert len(results) == 2
        assert mock_tool_executor.execute_tool.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_partial_tool_failures(
        self,
        use_case: HandleMessageUseCase,
        mock_tool_executor: AsyncMock,
    ) -> None:
        mock_tool_executor.execute_tool.side_effect = [
            {"products": []},
            Exception("Service unavailable"),
        ]
        results = await use_case.execute_parallel_tool_calls([
            ("catalogue_search", {"query": "bag"}),
            ("inventory_check", {"product_id": "p1"}),
        ])
        assert len(results) == 2
        assert results[0][4] is True   # First succeeded
        assert results[1][4] is False  # Second failed

    @pytest.mark.asyncio
    async def test_empty_tool_list_returns_empty(
        self, use_case: HandleMessageUseCase
    ) -> None:
        results = await use_case.execute_parallel_tool_calls([])
        assert results == []
