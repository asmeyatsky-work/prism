"""
Tests for the SearchSession aggregate root.

Tests cover:
- Session creation with identity and tenant scoping
- Adding queries and recording domain events
- Click tracking and engagement rate calculation
- Immutability — all mutations return new instances
- Anonymous vs authenticated session behaviour
"""

from __future__ import annotations

import pytest

from prism.discovery.domain.entities.search_session import SearchSession
from prism.discovery.domain.events.discovery_events import (
    SearchExecutedEvent,
    SearchResultClickedEvent,
)
from prism.discovery.domain.value_objects.search_query import (
    SearchModality,
    SearchQuery,
    SearchResult,
    SearchResultSet,
)
from prism.shared.domain.value_objects import Locale


# ── Fixtures ──────────────────────────────────────────────


def _make_session(
    session_id: str = "sess-001",
    tenant_id: str = "brand-gucci",
    customer_id: str | None = "cust-42",
) -> SearchSession:
    return SearchSession(
        session_id=session_id,
        tenant_id=tenant_id,
        customer_id=customer_id,
    )


def _make_query(text: str = "leather handbag") -> SearchQuery:
    return SearchQuery(
        text=text,
        modality=SearchModality.TEXT,
        locale=Locale(language="en"),
    )


def _make_result_set(count: int = 5) -> SearchResultSet:
    results = tuple(
        SearchResult(
            product_id=f"prod-{i}",
            score=1.0 - i * 0.1,
            rank=i + 1,
            explanation=f"match {i}",
        )
        for i in range(count)
    )
    return SearchResultSet(
        results=results,
        total_count=count,
        query_time_ms=42.5,
        search_type=SearchModality.TEXT,
    )


# ── Session Creation ──────────────────────────────────────


class TestSearchSessionCreation:
    def test_create_session_with_required_fields(self) -> None:
        session = _make_session()
        assert session.session_id == "sess-001"
        assert session.tenant_id == "brand-gucci"
        assert session.customer_id == "cust-42"

    def test_new_session_has_no_queries(self) -> None:
        session = _make_session()
        assert session.queries == ()
        assert session.query_count == 0

    def test_new_session_has_zero_engagement(self) -> None:
        session = _make_session()
        assert session.results_served == 0
        assert session.clicks == 0
        assert session.calculate_engagement_rate() == 0.0

    def test_anonymous_session(self) -> None:
        session = _make_session(customer_id=None)
        assert session.is_anonymous is True
        assert session.customer_id is None

    def test_authenticated_session(self) -> None:
        session = _make_session(customer_id="cust-42")
        assert session.is_anonymous is False


# ── Adding Queries ────────────────────────────────────────


class TestAddQuery:
    def test_add_query_appends_to_queries(self) -> None:
        session = _make_session()
        query = _make_query()
        result_set = _make_result_set(count=3)

        updated = session.add_query(query, result_set)

        assert updated.query_count == 1
        assert updated.queries[-1] is query

    def test_add_query_updates_results_served(self) -> None:
        session = _make_session()
        result_set = _make_result_set(count=10)

        updated = session.add_query(_make_query(), result_set)

        assert updated.results_served == 10

    def test_add_multiple_queries_accumulates(self) -> None:
        session = _make_session()
        q1 = _make_query("leather handbag")
        q2 = _make_query("silk scarf")
        rs1 = _make_result_set(count=5)
        rs2 = _make_result_set(count=3)

        updated = session.add_query(q1, rs1).add_query(q2, rs2)

        assert updated.query_count == 2
        assert updated.results_served == 8

    def test_add_query_produces_search_executed_event(self) -> None:
        session = _make_session()
        query = _make_query("evening gown")
        result_set = _make_result_set(count=7)

        updated = session.add_query(query, result_set)

        assert len(updated.domain_events) == 1
        event = updated.domain_events[0]
        assert isinstance(event, SearchExecutedEvent)
        assert event.tenant_id == "brand-gucci"
        assert event.query_text == "evening gown"
        assert event.modality == "TEXT"
        assert event.result_count == 7

    def test_add_query_preserves_immutability(self) -> None:
        session = _make_session()
        updated = session.add_query(_make_query(), _make_result_set())

        # Original is unchanged
        assert session.query_count == 0
        assert session.results_served == 0
        assert updated.query_count == 1

    def test_latest_query_returns_most_recent(self) -> None:
        session = _make_session()
        q1 = _make_query("first")
        q2 = _make_query("second")

        updated = session.add_query(q1, _make_result_set()).add_query(
            q2, _make_result_set()
        )

        assert updated.latest_query is not None
        assert updated.latest_query.text == "second"

    def test_latest_query_none_when_empty(self) -> None:
        session = _make_session()
        assert session.latest_query is None


# ── Click Tracking ────────────────────────────────────────


class TestRecordClick:
    def test_record_click_increments_count(self) -> None:
        session = _make_session()
        session = session.add_query(_make_query(), _make_result_set())

        updated = session.record_click("prod-0", result_rank=1)

        assert updated.clicks == 1

    def test_multiple_clicks_accumulate(self) -> None:
        session = _make_session()
        session = session.add_query(_make_query(), _make_result_set())

        updated = (
            session.record_click("prod-0", result_rank=1)
            .record_click("prod-1", result_rank=2)
            .record_click("prod-2", result_rank=3)
        )

        assert updated.clicks == 3

    def test_record_click_produces_event(self) -> None:
        session = _make_session()
        session = session.add_query(_make_query(), _make_result_set())
        # Clear the SearchExecutedEvent from add_query
        session = session.clear_events()

        updated = session.record_click("prod-0", result_rank=1)

        assert len(updated.domain_events) == 1
        event = updated.domain_events[0]
        assert isinstance(event, SearchResultClickedEvent)
        assert event.product_id == "prod-0"
        assert event.result_rank == 1
        assert event.tenant_id == "brand-gucci"

    def test_record_click_preserves_immutability(self) -> None:
        session = _make_session()
        session = session.add_query(_make_query(), _make_result_set())
        original_clicks = session.clicks

        updated = session.record_click("prod-0", result_rank=1)

        assert session.clicks == original_clicks
        assert updated.clicks == original_clicks + 1


# ── Engagement Rate ───────────────────────────────────────


class TestEngagementRate:
    def test_zero_results_returns_zero(self) -> None:
        session = _make_session()
        assert session.calculate_engagement_rate() == 0.0

    def test_no_clicks_returns_zero(self) -> None:
        session = _make_session().add_query(_make_query(), _make_result_set(count=10))
        assert session.calculate_engagement_rate() == 0.0

    def test_some_clicks_computes_rate(self) -> None:
        session = _make_session().add_query(_make_query(), _make_result_set(count=10))
        session = session.record_click("prod-0", 1).record_click("prod-1", 2)

        rate = session.calculate_engagement_rate()

        assert rate == pytest.approx(0.2)  # 2 clicks / 10 results

    def test_rate_capped_at_one(self) -> None:
        # Edge case: more clicks than results served (shouldn't happen in
        # practice, but the domain guards against it)
        session = _make_session().add_query(_make_query(), _make_result_set(count=1))
        session = session.record_click("prod-0", 1).record_click("prod-0", 1)

        rate = session.calculate_engagement_rate()

        assert rate <= 1.0


# ── Domain Events ─────────────────────────────────────────


class TestDomainEvents:
    def test_clear_events_removes_all(self) -> None:
        session = _make_session().add_query(_make_query(), _make_result_set())
        assert len(session.domain_events) > 0

        cleared = session.clear_events()
        assert len(cleared.domain_events) == 0

    def test_events_accumulate_across_operations(self) -> None:
        session = _make_session()
        session = session.add_query(_make_query(), _make_result_set())
        session = session.record_click("prod-0", 1)

        assert len(session.domain_events) == 2
        assert isinstance(session.domain_events[0], SearchExecutedEvent)
        assert isinstance(session.domain_events[1], SearchResultClickedEvent)
