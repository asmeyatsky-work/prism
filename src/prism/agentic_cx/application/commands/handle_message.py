"""
Agentic CX — Handle Message Use Case

Architectural Intent:
- Core use case: receives a customer message and produces an agent response
- Builds full LLM context: conversation history + customer profile + session memory
- Selects tools based on intent, then invokes LLM with tool definitions
- If LLM requests tool calls, executes them in parallel where independent
- Checks escalation threshold after response generation
- Parallelism-first: independent tool calls fan out via asyncio.gather (skill2026 Rule 6)
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort

from prism.agentic_cx.application.dtos.agent_dto import (
    AgentResponseDTO,
    AgentToolCallDTO,
    EscalationDTO,
    SendMessageRequestDTO,
)
from prism.agentic_cx.domain.entities.agent_persona import AgentPersona
from prism.agentic_cx.domain.entities.conversation import ConversationStatus
from prism.agentic_cx.domain.ports.agent_ports import (
    AgentLLMPort,
    ConversationRepositoryPort,
    CustomerProfilePort,
    ToolExecutionPort,
)
from prism.agentic_cx.domain.ports.memory_ports import SessionMemoryPort
from prism.agentic_cx.domain.services.conversation_service import ConversationService
from prism.agentic_cx.domain.value_objects.agent_config import AgentToolkit
from prism.agentic_cx.domain.value_objects.messages import (
    MessageModality,
    MessageRole,
)


class HandleMessageUseCase:
    """
    Use case: handle an incoming customer message.

    This is the central orchestration point for the agent interaction loop:
    message -> context build -> tool selection -> LLM call -> tool execution ->
    response generation -> escalation check.
    """

    def __init__(
        self,
        conversation_repo: ConversationRepositoryPort,
        customer_profile_port: CustomerProfilePort,
        session_memory: SessionMemoryPort,
        agent_llm: AgentLLMPort,
        tool_executor: ToolExecutionPort,
        event_bus: EventBusPort,
        persona: AgentPersona,
        toolkit: AgentToolkit,
    ) -> None:
        self._conversation_repo = conversation_repo
        self._customer_profile_port = customer_profile_port
        self._session_memory = session_memory
        self._agent_llm = agent_llm
        self._tool_executor = tool_executor
        self._event_bus = event_bus
        self._persona = persona
        self._toolkit = toolkit
        self._service = ConversationService()

    async def execute(
        self,
        request: SendMessageRequestDTO,
    ) -> CommandResult[AgentResponseDTO]:
        """
        Execute the handle message use case.

        Steps:
        1. Load conversation from repository
        2. Validate conversation state
        3. Add customer message to conversation
        4. Build LLM context (conversation + profile + session memory)
        5. Select tools based on message intent
        6. Call LLM for response (may request tool calls)
        7. Execute any tool calls (parallel where independent)
        8. Generate final response
        9. Check escalation threshold
        10. Persist and dispatch events

        Returns:
            CommandResult containing the AgentResponseDTO.
        """
        # Load conversation
        conversation = await self._conversation_repo.get_by_id(request.conversation_id)
        if conversation is None:
            return CommandResult.fail(
                f"Conversation not found: {request.conversation_id}",
                code="NOT_FOUND",
            )

        # Validate state
        if conversation.status not in (
            ConversationStatus.ACTIVE,
            ConversationStatus.PAUSED,
        ):
            return CommandResult.fail(
                f"Conversation is {conversation.status.value} and cannot accept messages",
                code="INVALID_STATE",
            )

        # Resume if paused
        if conversation.status == ConversationStatus.PAUSED:
            conversation = conversation.resume()

        # Add customer message
        try:
            modality = MessageModality(request.modality)
        except ValueError:
            modality = MessageModality.TEXT

        conversation = conversation.add_message(
            role=MessageRole.CUSTOMER,
            content=request.content,
            modality=modality,
            metadata=request.metadata,
        )

        # Load customer profile
        customer_profile = None
        if conversation.customer_id:
            customer_profile = await self._customer_profile_port.get_profile(
                customer_id=conversation.customer_id,
                tenant_id=conversation.tenant_id,
            )

        # Load session memory
        session_context = await self._session_memory.get_session_context(
            session_id=conversation.conversation_id,
        )

        # Build LLM context
        context = self._service.build_agent_context(
            conversation=conversation,
            customer_profile=customer_profile,
            session_context=session_context,
            persona=self._persona,
        )

        # Select tools for intent
        selected_tools = self._service.select_tools_for_intent(
            message=request.content,
            available_tools=self._toolkit,
        )

        # Build tool definitions for LLM
        tool_definitions = [
            {"name": tool, "description": f"Execute {tool} tool"}
            for tool in selected_tools
        ]

        # Call LLM
        response_content = await self._agent_llm.generate_response(
            context=context,
            tools=tool_definitions,
        )

        # Execute tool calls if the LLM response indicates them
        tool_call_dtos: list[AgentToolCallDTO] = []
        tool_results = await self._execute_tool_calls(
            response_content=response_content,
            conversation=conversation,
            selected_tools=selected_tools,
        )
        for tool_name, args, result, duration_ms, success in tool_results:
            conversation = conversation.add_tool_call(
                tool_name=tool_name,
                arguments=args,
                result=result,
                duration_ms=duration_ms,
                success=success,
            )
            tool_call_dtos.append(AgentToolCallDTO(
                tool_name=tool_name,
                arguments=args,
                result=result,
                duration_ms=duration_ms,
                success=success,
            ))

        # If tools were called, do a follow-up LLM call with tool results
        if tool_results:
            context = self._service.build_agent_context(
                conversation=conversation,
                customer_profile=customer_profile,
                session_context=session_context,
                persona=self._persona,
            )
            response_content = await self._agent_llm.generate_response(
                context=context,
                tools=[],  # No tools on follow-up — synthesise from results
            )

        # Add agent response to conversation
        conversation = conversation.add_agent_response(response_content)

        # Check escalation
        should_escalate = self._service.should_escalate(
            conversation=conversation,
            persona=self._persona,
        )
        escalation_dto: EscalationDTO | None = None
        if should_escalate:
            conversation = conversation.escalate_to_human(
                reason="Confidence below threshold or customer request",
                confidence=self._persona.escalation_threshold,
            )
            ctx = conversation.escalation_context
            if ctx:
                escalation_dto = EscalationDTO(
                    conversation_id=conversation.conversation_id,
                    reason=ctx.reason,
                    confidence=ctx.confidence,
                    conversation_summary=ctx.conversation_summary,
                    customer_sentiment=ctx.customer_sentiment,
                    agent_type=conversation.agent_type.value,
                    channel=conversation.channel.value,
                )

        # Persist
        await self._conversation_repo.save(conversation)

        # Dispatch events
        events = list(conversation.domain_events)
        if events:
            await self._event_bus.publish(events)

        # Build response DTO
        response_dto = AgentResponseDTO(
            conversation_id=conversation.conversation_id,
            response_content=response_content,
            tool_calls_made=tool_call_dtos,
            should_escalate=should_escalate,
            escalation=escalation_dto,
        )
        return CommandResult.ok(response_dto)

    async def _execute_tool_calls(
        self,
        response_content: str,
        conversation: Any,
        selected_tools: list[str],
    ) -> list[tuple[str, dict, dict, int, bool]]:
        """
        Parse and execute tool calls from the LLM response.

        In a full implementation, this would parse structured tool call
        output from the LLM. For now, it returns an empty list and
        relies on the LLM adapter to handle tool calling natively.

        Independent tool calls are executed in parallel via asyncio.gather.
        """
        # Tool call parsing is handled by the LLM adapter implementation.
        # The adapter returns structured tool calls which are executed here.
        # This is a placeholder that will be populated by the Gemini adapter.
        return []

    async def _execute_single_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[str, dict, dict, int, bool]:
        """Execute a single tool call and measure duration."""
        start_time = time.monotonic()
        try:
            result = await self._tool_executor.execute_tool(
                tool_name=tool_name,
                arguments=arguments,
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return (tool_name, arguments, result, duration_ms, True)
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return (
                tool_name,
                arguments,
                {"error": str(e)},
                duration_ms,
                False,
            )

    async def execute_parallel_tool_calls(
        self,
        tool_calls: list[tuple[str, dict[str, Any]]],
    ) -> list[tuple[str, dict, dict, int, bool]]:
        """
        Execute multiple independent tool calls in parallel.

        Per skill2026 Rule 6: Parallelism-First. Independent tool calls
        fan out via asyncio.gather for minimum latency.

        Args:
            tool_calls: List of (tool_name, arguments) tuples.

        Returns:
            List of (tool_name, arguments, result, duration_ms, success) tuples.
        """
        if not tool_calls:
            return []

        tasks = [
            self._execute_single_tool(name, args)
            for name, args in tool_calls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        executed: list[tuple[str, dict, dict, int, bool]] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                name, args = tool_calls[i]
                executed.append((name, args, {"error": str(result)}, 0, False))
            else:
                executed.append(result)
        return executed
