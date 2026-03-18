"""
Try-On Application Query — Get Try-On Result

Architectural Intent:
- Read-only query to retrieve a completed try-on session result
- Returns QueryResult with TryOnResponseDTO
- Designed for MCP resource access pattern: tryon://result/{session_id}
- Requires a session repository port for persistence lookup
"""

from __future__ import annotations

from typing import Protocol

from prism.shared.application.dtos import QueryResult
from prism.shared.domain.value_objects import TenantId

from prism.tryon.application.dtos.tryon_dto import TryOnResponseDTO
from prism.tryon.domain.entities.tryon_session import TryOnSession, TryOnStatus
from prism.tryon.domain.services.tryon_validation_service import TryOnValidationService


class TryOnSessionRepository(Protocol):
    """Repository port for TryOnSession persistence (read path)."""

    async def get_by_id(self, session_id: str, tenant_id: TenantId) -> TryOnSession | None: ...


class GetTryOnResultQuery:
    """
    Query handler: retrieve a completed try-on result by session ID.

    Returns the composited try-on result if the session exists and is COMPLETED.
    """

    def __init__(
        self,
        repository: TryOnSessionRepository,
        validation_service: TryOnValidationService | None = None,
    ) -> None:
        self._repository = repository
        self._validation = validation_service or TryOnValidationService()

    async def execute(
        self,
        session_id: str,
        tenant_id: str,
    ) -> QueryResult[TryOnResponseDTO]:
        """
        Retrieve a try-on result.

        Args:
            session_id: The session to look up.
            tenant_id: Tenant scope for multi-tenant isolation.

        Returns:
            QueryResult containing TryOnResponseDTO if found and completed,
            or an appropriate error/empty result otherwise.
        """
        session = await self._repository.get_by_id(
            session_id=session_id,
            tenant_id=TenantId(value=tenant_id),
        )

        if session is None:
            return QueryResult.fail(f"Try-on session '{session_id}' not found")

        if session.status != TryOnStatus.COMPLETED:
            return QueryResult.fail(
                f"Try-on session '{session_id}' is not completed "
                f"(status: {session.status.value})"
            )

        if session.composition_result is None:
            return QueryResult.fail(
                f"Try-on session '{session_id}' has no composition result"
            )

        within_budget = self._validation.validate_latency_budget(
            session.processing_time_ms
        )

        response = TryOnResponseDTO(
            session_id=session.id,
            product_id=session.product_id,
            result_image_url=session.composition_result.result_image_url,
            confidence=session.composition_result.confidence,
            processing_time_ms=session.processing_time_ms,
            within_latency_budget=within_budget,
        )

        return QueryResult.ok(data=response, total_count=1)
