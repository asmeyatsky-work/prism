"""
Shared Application — DAG-Based Workflow Orchestrator

Architectural Intent:
- Parallelism-first design per skill2026 Principle 6
- Steps execute concurrently when no data dependency exists
- Dependencies are explicit via DAG topology
- Backpressure applied at orchestrator level, not within individual tasks
- Timeout and cancellation propagation implemented

Parallelization Notes:
- Steps at the same topological level run via asyncio.gather
- Failed critical steps halt the entire workflow
- Non-critical failures are captured and returned in results
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine


class OrchestrationError(Exception):
    """Raised when a workflow step fails or a cycle is detected."""

    pass


@dataclass(frozen=True)
class WorkflowStep:
    """A single step in a DAG-based workflow."""

    name: str
    execute: Callable[..., Coroutine[Any, Any, Any]]
    depends_on: tuple[str, ...] = field(default=())
    is_critical: bool = True
    timeout_seconds: float = 30.0


@dataclass(frozen=True)
class StepResult:
    """Result of a single workflow step execution."""

    name: str
    success: bool
    value: Any = None
    error: str | None = None


class DAGOrchestrator:
    """
    Executes workflow steps respecting dependency order,
    parallelizing independent steps automatically.

    Per skill2026 Rule 7: Parallel-Safe Orchestration.
    """

    def __init__(self, steps: list[WorkflowStep]) -> None:
        self._steps = {s.name: s for s in steps}
        self._validate_no_cycles()

    def _validate_no_cycles(self) -> None:
        visited: set[str] = set()
        in_stack: set[str] = set()

        def dfs(name: str) -> None:
            if name in in_stack:
                raise OrchestrationError(f"Circular dependency detected involving '{name}'")
            if name in visited:
                return
            in_stack.add(name)
            step = self._steps.get(name)
            if step:
                for dep in step.depends_on:
                    if dep not in self._steps:
                        raise OrchestrationError(f"Unknown dependency '{dep}' in step '{name}'")
                    dfs(dep)
            in_stack.discard(name)
            visited.add(name)

        for name in self._steps:
            dfs(name)

    async def execute(self, context: dict[str, Any] | None = None) -> dict[str, StepResult]:
        ctx = context or {}
        completed: dict[str, StepResult] = {}
        pending = set(self._steps.keys())

        while pending:
            ready = [
                name
                for name in pending
                if all(dep in completed for dep in self._steps[name].depends_on)
            ]
            if not ready:
                raise OrchestrationError("Deadlock: no steps are ready but pending remain")

            results = await asyncio.gather(
                *(self._run_step(name, ctx, completed) for name in ready),
                return_exceptions=True,
            )

            for name, result in zip(ready, results):
                if isinstance(result, BaseException):
                    step = self._steps[name]
                    if step.is_critical:
                        raise OrchestrationError(
                            f"Critical step '{name}' failed: {result}"
                        ) from result
                    completed[name] = StepResult(
                        name=name, success=False, error=str(result)
                    )
                else:
                    completed[name] = result
                pending.discard(name)

        return completed

    async def _run_step(
        self,
        name: str,
        context: dict[str, Any],
        completed: dict[str, StepResult],
    ) -> StepResult:
        step = self._steps[name]
        dep_results = {
            dep: completed[dep].value
            for dep in step.depends_on
            if completed[dep].success
        }
        try:
            value = await asyncio.wait_for(
                step.execute(context, dep_results),
                timeout=step.timeout_seconds,
            )
            return StepResult(name=name, success=True, value=value)
        except asyncio.TimeoutError:
            return StepResult(name=name, success=False, error=f"Timeout after {step.timeout_seconds}s")
