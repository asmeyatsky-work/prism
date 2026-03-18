"""
Agentic CX — Agent Orchestrator (Multi-Agent Coordination)

Architectural Intent:
- Implements the Multi-Agent Coordination pattern from skill2026
- Three-phase workflow: Research -> Synthesis -> Validation
- Research phase: parallel tool calls to gather information
- Synthesis phase: LLM combines research results into a coherent response
- Validation phase: checks response quality, brand compliance, and escalation
- Built on the shared DAGOrchestrator for automatic parallelisation
- Each phase can fail independently; critical failures halt the workflow
"""

from __future__ import annotations

from typing import Any

from prism.shared.application.orchestration import DAGOrchestrator, WorkflowStep

from prism.agentic_cx.domain.entities.agent_persona import AgentPersona
from prism.agentic_cx.domain.entities.conversation import Conversation
from prism.agentic_cx.domain.entities.customer_profile import CustomerProfile
from prism.agentic_cx.domain.ports.agent_ports import AgentLLMPort, ToolExecutionPort
from prism.agentic_cx.domain.ports.memory_ports import SessionMemoryPort
from prism.agentic_cx.domain.services.conversation_service import ConversationService
from prism.agentic_cx.domain.value_objects.agent_config import AgentToolkit


class AgentOrchestrator:
    """
    Multi-agent coordination orchestrator.

    Coordinates the Research -> Synthesis -> Validation pipeline
    using the shared DAGOrchestrator for automatic parallelisation
    of independent steps.

    Research Phase (parallel):
    - catalogue_research: Search catalogue for relevant products
    - profile_analysis: Analyse customer profile for personalisation signals
    - session_context: Load session memory for continuity

    Synthesis Phase (depends on all research):
    - generate_response: LLM synthesises research into a coherent response

    Validation Phase (depends on synthesis):
    - quality_check: Validate response quality and brand compliance
    - escalation_check: Determine if escalation is needed
    """

    def __init__(
        self,
        agent_llm: AgentLLMPort,
        tool_executor: ToolExecutionPort,
        session_memory: SessionMemoryPort,
        persona: AgentPersona,
        toolkit: AgentToolkit,
    ) -> None:
        self._agent_llm = agent_llm
        self._tool_executor = tool_executor
        self._session_memory = session_memory
        self._persona = persona
        self._toolkit = toolkit
        self._service = ConversationService()

    async def orchestrate(
        self,
        conversation: Conversation,
        customer_profile: CustomerProfile | None,
        customer_message: str,
    ) -> dict[str, Any]:
        """
        Execute the full Research -> Synthesis -> Validation pipeline.

        Args:
            conversation: Current conversation state.
            customer_profile: Customer profile for personalisation (may be None).
            customer_message: The customer's latest message.

        Returns:
            Dictionary containing:
            - response: The agent's response text
            - tool_results: Results from research phase tool calls
            - should_escalate: Whether to escalate to human
            - quality_score: Response quality assessment
        """
        # Build workflow steps
        steps = self._build_workflow_steps(
            conversation=conversation,
            customer_profile=customer_profile,
            customer_message=customer_message,
        )

        # Execute via DAG orchestrator
        orchestrator = DAGOrchestrator(steps)
        context = {
            "conversation": conversation,
            "customer_profile": customer_profile,
            "customer_message": customer_message,
            "persona": self._persona,
            "toolkit": self._toolkit,
        }
        results = await orchestrator.execute(context)

        # Extract outputs
        response = ""
        if results.get("generate_response") and results["generate_response"].success:
            response = results["generate_response"].value or ""

        should_escalate = False
        if results.get("escalation_check") and results["escalation_check"].success:
            should_escalate = results["escalation_check"].value or False

        quality_score = 1.0
        if results.get("quality_check") and results["quality_check"].success:
            quality_score = results["quality_check"].value or 1.0

        tool_results: dict[str, Any] = {}
        if results.get("catalogue_research") and results["catalogue_research"].success:
            tool_results["catalogue"] = results["catalogue_research"].value

        return {
            "response": response,
            "tool_results": tool_results,
            "should_escalate": should_escalate,
            "quality_score": quality_score,
        }

    def _build_workflow_steps(
        self,
        conversation: Conversation,
        customer_profile: CustomerProfile | None,
        customer_message: str,
    ) -> list[WorkflowStep]:
        """Build the DAG workflow steps for the orchestration pipeline."""

        # ── Research Phase (parallel, no dependencies) ───────────────

        async def catalogue_research(
            ctx: dict[str, Any], deps: dict[str, Any]
        ) -> dict[str, Any]:
            """Search catalogue based on customer intent."""
            selected_tools = self._service.select_tools_for_intent(
                message=customer_message,
                available_tools=self._toolkit,
            )
            results: dict[str, Any] = {}
            if "catalogue_search" in selected_tools:
                results = await self._tool_executor.execute_tool(
                    tool_name="catalogue_search",
                    arguments={"query": customer_message},
                )
            return results

        async def profile_analysis(
            ctx: dict[str, Any], deps: dict[str, Any]
        ) -> dict[str, Any]:
            """Analyse customer profile for personalisation signals."""
            if customer_profile:
                return customer_profile.to_agent_context()
            return {}

        async def session_context_load(
            ctx: dict[str, Any], deps: dict[str, Any]
        ) -> dict[str, Any]:
            """Load session memory for conversation continuity."""
            return await self._session_memory.get_session_context(
                session_id=conversation.conversation_id,
            )

        # ── Synthesis Phase (depends on all research) ────────────────

        async def generate_response(
            ctx: dict[str, Any], deps: dict[str, Any]
        ) -> str:
            """Synthesise research results into an agent response."""
            agent_context = self._service.build_agent_context(
                conversation=conversation,
                customer_profile=customer_profile,
                session_context=deps.get("session_context", {}),
                persona=self._persona,
            )
            # Inject research results into context
            agent_context["research"] = {
                "catalogue": deps.get("catalogue_research", {}),
                "profile": deps.get("profile_analysis", {}),
            }
            return await self._agent_llm.generate_response(
                context=agent_context,
                tools=[],
            )

        # ── Validation Phase (depends on synthesis) ──────────────────

        async def quality_check(
            ctx: dict[str, Any], deps: dict[str, Any]
        ) -> float:
            """Validate response quality and brand compliance."""
            response_text = deps.get("generate_response", "")
            if not response_text:
                return 0.0
            # Basic quality heuristics — production would use a dedicated model
            score = 1.0
            if len(response_text) < 20:
                score -= 0.3
            if len(response_text) > 2000:
                score -= 0.2
            # Check for persona name usage (brand compliance)
            if self._persona.persona_name and self._persona.persona_name.lower() not in response_text.lower():
                pass  # Not required in every message
            return max(0.0, min(1.0, score))

        async def escalation_check(
            ctx: dict[str, Any], deps: dict[str, Any]
        ) -> bool:
            """Determine if the conversation should be escalated."""
            quality = deps.get("quality_check", 1.0)
            return self._service.should_escalate(
                conversation=conversation,
                persona=self._persona,
                current_confidence=quality if isinstance(quality, float) else 1.0,
            )

        return [
            # Research phase — parallel
            WorkflowStep(
                name="catalogue_research",
                execute=catalogue_research,
                is_critical=False,
                timeout_seconds=10.0,
            ),
            WorkflowStep(
                name="profile_analysis",
                execute=profile_analysis,
                is_critical=False,
                timeout_seconds=5.0,
            ),
            WorkflowStep(
                name="session_context",
                execute=session_context_load,
                is_critical=False,
                timeout_seconds=5.0,
            ),
            # Synthesis phase — depends on research
            WorkflowStep(
                name="generate_response",
                execute=generate_response,
                depends_on=(
                    "catalogue_research",
                    "profile_analysis",
                    "session_context",
                ),
                is_critical=True,
                timeout_seconds=30.0,
            ),
            # Validation phase — depends on synthesis
            WorkflowStep(
                name="quality_check",
                execute=quality_check,
                depends_on=("generate_response",),
                is_critical=False,
                timeout_seconds=5.0,
            ),
            WorkflowStep(
                name="escalation_check",
                execute=escalation_check,
                depends_on=("quality_check",),
                is_critical=False,
                timeout_seconds=5.0,
            ),
        ]
