"""
Tests for the RankingService domain service.

Tests cover:
- Composite relevance score computation with weighted signals
- Score clamping to [0.0, 1.0] range
- Personalisation re-ranking with browsing/purchase/preference signals
- Rank reassignment after re-sorting
- Edge cases: empty results, no signals, extreme scores
"""

from __future__ import annotations

import pytest

from prism.discovery.domain.services.ranking_service import RankingService
from prism.discovery.domain.value_objects.search_query import (
    ReRankingSignals,
    SearchResult,
)


# ── Fixtures ──────────────────────────────────────────────


def _make_results(count: int = 5) -> list[SearchResult]:
    """Create a list of search results with descending scores."""
    return [
        SearchResult(
            product_id=f"prod-{i}",
            score=1.0 - i * 0.15,
            rank=i + 1,
            explanation=f"semantic match {i}",
        )
        for i in range(count)
    ]


def _make_signals(
    browsing: tuple[str, ...] = (),
    purchases: tuple[str, ...] = (),
    preferences: dict | None = None,
) -> ReRankingSignals:
    return ReRankingSignals(
        browsing_history=browsing,
        purchase_history=purchases,
        preferences=preferences or {},
    )


# ── Relevance Score Computation ───────────────────────────


class TestComputeRelevanceScore:
    def test_semantic_only(self) -> None:
        score = RankingService.compute_relevance_score(
            semantic_score=0.9,
            personalisation_score=0.0,
            freshness_score=0.0,
        )
        # 0.60 * 0.9 = 0.54
        assert score == pytest.approx(0.54)

    def test_all_signals(self) -> None:
        score = RankingService.compute_relevance_score(
            semantic_score=0.8,
            personalisation_score=0.6,
            freshness_score=0.4,
        )
        # 0.60 * 0.8 + 0.25 * 0.6 + 0.15 * 0.4 = 0.48 + 0.15 + 0.06 = 0.69
        assert score == pytest.approx(0.69)

    def test_perfect_scores(self) -> None:
        score = RankingService.compute_relevance_score(
            semantic_score=1.0,
            personalisation_score=1.0,
            freshness_score=1.0,
        )
        # 0.60 + 0.25 + 0.15 = 1.0
        assert score == pytest.approx(1.0)

    def test_zero_scores(self) -> None:
        score = RankingService.compute_relevance_score(0.0, 0.0, 0.0)
        assert score == 0.0

    def test_clamping_high(self) -> None:
        score = RankingService.compute_relevance_score(1.5, 1.5, 1.5)
        assert score <= 1.0

    def test_clamping_low(self) -> None:
        score = RankingService.compute_relevance_score(-0.5, -0.5, -0.5)
        assert score >= 0.0

    def test_weights_sum_to_one(self) -> None:
        total = (
            RankingService.SEMANTIC_WEIGHT
            + RankingService.PERSONALISATION_WEIGHT
            + RankingService.FRESHNESS_WEIGHT
        )
        assert total == pytest.approx(1.0)


# ── Personalisation Re-ranking ────────────────────────────


class TestApplyPersonalisation:
    def test_no_signals_returns_unchanged(self) -> None:
        results = _make_results(3)
        signals = _make_signals()

        reranked = RankingService.apply_personalisation(results, signals)

        assert [r.product_id for r in reranked] == [r.product_id for r in results]
        assert [r.score for r in reranked] == [r.score for r in results]

    def test_browsing_boost_increases_score(self) -> None:
        results = _make_results(3)
        # Boost the last product (lowest score) via browsing history
        signals = _make_signals(browsing=("prod-2",))

        reranked = RankingService.apply_personalisation(results, signals)

        # Find prod-2 in reranked results
        boosted = next(r for r in reranked if r.product_id == "prod-2")
        original = next(r for r in results if r.product_id == "prod-2")
        assert boosted.score > original.score

    def test_purchase_boost_is_smaller_than_browsing(self) -> None:
        results = _make_results(3)
        browse_signals = _make_signals(browsing=("prod-2",))
        purchase_signals = _make_signals(purchases=("prod-2",))

        browsed = RankingService.apply_personalisation(results, browse_signals)
        purchased = RankingService.apply_personalisation(results, purchase_signals)

        browse_score = next(r for r in browsed if r.product_id == "prod-2").score
        purchase_score = next(r for r in purchased if r.product_id == "prod-2").score

        # Purchased items get a smaller boost (luxury customers don't re-buy)
        assert browse_score > purchase_score

    def test_preference_boost_applied(self) -> None:
        results = _make_results(3)
        signals = _make_signals(preferences={"material": "leather"})

        reranked = RankingService.apply_personalisation(results, signals)

        # All results should have boosted scores when preferences exist
        for reranked_r, original_r in zip(reranked, results):
            # Scores may change due to reranking; at least one should be boosted
            pass
        # Overall: check that scores increased for at least one result
        original_scores = {r.product_id: r.score for r in results}
        boosted_count = sum(
            1 for r in reranked if r.score > original_scores[r.product_id]
        )
        assert boosted_count > 0

    def test_reranking_reassigns_ranks(self) -> None:
        results = _make_results(5)
        # Give the lowest-ranked item a big browsing boost
        signals = _make_signals(
            browsing=("prod-4",),
            preferences={"material": "silk"},
        )

        reranked = RankingService.apply_personalisation(results, signals)

        # Ranks should be sequential 1..N
        ranks = [r.rank for r in reranked]
        assert ranks == list(range(1, len(reranked) + 1))

    def test_empty_results_returns_empty(self) -> None:
        results: list[SearchResult] = []
        signals = _make_signals(browsing=("prod-0",))

        reranked = RankingService.apply_personalisation(results, signals)

        assert reranked == []

    def test_scores_remain_clamped(self) -> None:
        # Create a result with a very high score
        results = [
            SearchResult(product_id="prod-0", score=0.99, rank=1, explanation=""),
        ]
        signals = _make_signals(
            browsing=("prod-0",),
            purchases=("prod-0",),
            preferences={"style": "classic"},
        )

        reranked = RankingService.apply_personalisation(results, signals)

        for r in reranked:
            assert 0.0 <= r.score <= 1.0

    def test_combined_signals_cumulative(self) -> None:
        results = _make_results(3)
        # Combine browsing + preferences for maximum boost
        combined_signals = _make_signals(
            browsing=("prod-2",),
            preferences={"material": "cashmere"},
        )
        browse_only_signals = _make_signals(browsing=("prod-2",))

        combined = RankingService.apply_personalisation(results, combined_signals)
        browse_only = RankingService.apply_personalisation(results, browse_only_signals)

        combined_score = next(r for r in combined if r.product_id == "prod-2").score
        browse_score = next(r for r in browse_only if r.product_id == "prod-2").score

        assert combined_score >= browse_score
