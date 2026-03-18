"""
Discovery Entity — SearchSession Aggregate Root.

Architectural Intent:
- SearchSession is the primary aggregate for the Discovery bounded context
- Tracks a customer's search journey: queries issued, results served, clicks
- Immutable via frozen dataclass — state transitions produce new instances
- Domain events are collected and dispatched after persistence
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from prism.shared.domain.entities import AggregateRoot

from prism.discovery.domain.events.discovery_events import (
    SearchExecutedEvent,
    SearchResultClickedEvent,
)
from prism.discovery.domain.value_objects.search_query import (
    SearchQuery,
    SearchResultSet,
)


@dataclass(frozen=True)
class SearchSession(AggregateRoot):
    """
    Aggregate root tracking a customer's search session.

    A session begins when a customer initiates their first search and
    accumulates queries, results, and clicks. Engagement rate is a
    key metric for luxury retail — low engagement may indicate poor
    search relevance or catalogue gaps.
    """

    session_id: str = ""
    tenant_id: str = ""
    customer_id: str | None = None
    queries: tuple[SearchQuery, ...] = ()
    result_sets: tuple[SearchResultSet, ...] = ()
    results_served: int = 0
    clicks: int = 0

    def add_query(
        self,
        query: SearchQuery,
        result_set: SearchResultSet,
    ) -> SearchSession:
        """Record a search query and its results within this session."""
        new_session = replace(
            self,
            queries=self.queries + (query,),
            result_sets=self.result_sets + (result_set,),
            results_served=self.results_served + result_set.total_count,
            **self._touch(),
        )
        event = SearchExecutedEvent(
            aggregate_id=self.session_id,
            tenant_id=self.tenant_id,
            customer_id=self.customer_id or "",
            query_text=query.text or "",
            modality=query.modality.value,
            result_count=result_set.total_count,
            query_time_ms=result_set.query_time_ms,
        )
        return replace(
            new_session,
            domain_events=new_session.domain_events + (event,),
        )

    def record_click(self, product_id: str, result_rank: int) -> SearchSession:
        """Record that a customer clicked on a search result."""
        new_session = replace(
            self,
            clicks=self.clicks + 1,
            **self._touch(),
        )
        event = SearchResultClickedEvent(
            aggregate_id=self.session_id,
            tenant_id=self.tenant_id,
            customer_id=self.customer_id or "",
            product_id=product_id,
            result_rank=result_rank,
            session_query_count=len(self.queries),
        )
        return replace(
            new_session,
            domain_events=new_session.domain_events + (event,),
        )

    def calculate_engagement_rate(self) -> float:
        """
        Calculate the click-through engagement rate for this session.

        Returns a float between 0.0 and 1.0. A rate of 0.0 indicates
        no clicks at all; 1.0 means every result served was clicked.
        """
        if self.results_served == 0:
            return 0.0
        return min(self.clicks / self.results_served, 1.0)

    @property
    def query_count(self) -> int:
        return len(self.queries)

    @property
    def is_anonymous(self) -> bool:
        return self.customer_id is None

    @property
    def latest_query(self) -> SearchQuery | None:
        return self.queries[-1] if self.queries else None
