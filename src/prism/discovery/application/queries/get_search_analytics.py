"""
Discovery Query — Get Search Analytics for a session.

Architectural Intent:
- Provides read-only analytics for a search session
- Engagement metrics help luxury brands understand search effectiveness
- Session-level analytics feed into Intelligence context for aggregation
"""

from __future__ import annotations

import logging

from prism.shared.application.dtos import QueryResult

from prism.discovery.application.dtos.search_dto import SearchAnalyticsDTO
from prism.discovery.domain.entities.search_session import SearchSession

logger = logging.getLogger(__name__)


class GetSearchAnalyticsQuery:
    """
    Query handler that returns analytics for a search session.

    In a full implementation, this would retrieve the session from a
    repository. This implementation accepts a session directly for
    domain-level analytics computation.
    """

    def __init__(
        self,
        session_store: dict[str, SearchSession] | None = None,
    ) -> None:
        self._store = session_store or {}

    async def execute(
        self,
        session_id: str,
        tenant_id: str,
    ) -> QueryResult[SearchAnalyticsDTO]:
        """Return analytics for the specified search session."""
        session = self._store.get(session_id)

        if session is None:
            return QueryResult.fail(
                error=f"Session {session_id} not found",
            )

        if session.tenant_id != tenant_id:
            return QueryResult.fail(
                error="Session does not belong to the specified tenant",
            )

        modalities_used = list(
            {q.modality.value for q in session.queries}
        )

        analytics = SearchAnalyticsDTO(
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            query_count=session.query_count,
            total_results_served=session.results_served,
            total_clicks=session.clicks,
            engagement_rate=session.calculate_engagement_rate(),
            modalities_used=sorted(modalities_used),
        )

        return QueryResult.ok(data=analytics)
