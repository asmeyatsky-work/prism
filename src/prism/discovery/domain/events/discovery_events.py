"""
Discovery Domain Events — Published on search lifecycle state transitions.

Architectural Intent:
- Events enable loose coupling between Discovery and downstream contexts
- SearchExecutedEvent is consumed by Intelligence for analytics aggregation
- SearchResultClickedEvent feeds the personalisation learning loop
- FacetsGeneratedEvent allows Catalogue to track which facets are active
- All events carry tenant_id for multi-tenant routing via EventBusPort
"""

from __future__ import annotations

from dataclasses import dataclass

from prism.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class SearchExecutedEvent(DomainEvent):
    """Published when a search query is executed and results are returned."""

    customer_id: str = ""
    query_text: str = ""
    modality: str = "TEXT"
    result_count: int = 0
    query_time_ms: float = 0.0


@dataclass(frozen=True)
class SearchResultClickedEvent(DomainEvent):
    """Published when a customer clicks on a search result."""

    customer_id: str = ""
    product_id: str = ""
    result_rank: int = 0
    session_query_count: int = 0


@dataclass(frozen=True)
class FacetsGeneratedEvent(DomainEvent):
    """Published when facets are computed for a search result set."""

    facet_names: tuple[str, ...] = ()
    total_facet_values: int = 0
    search_session_id: str = ""
