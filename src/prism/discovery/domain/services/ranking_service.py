"""
Discovery Domain Service — Ranking and relevance computation.

Architectural Intent:
- Pure domain service with no infrastructure dependencies
- Encapsulates the scoring algorithm for search result ranking
- Personalisation re-ranking adjusts scores based on customer signals
- Weights are tunable per brand but defaults reflect luxury retail heuristics

Ranking Philosophy:
- Semantic relevance is the primary signal (what the customer asked for)
- Personalisation adjusts within a relevance band (never overrides strong relevance)
- Freshness provides a gentle boost for new arrivals (luxury customers value novelty)
"""

from __future__ import annotations

from dataclasses import replace

from prism.discovery.domain.value_objects.search_query import (
    ReRankingSignals,
    SearchResult,
)


class RankingService:
    """
    Domain service for computing relevance scores and applying
    personalisation re-ranking to search results.
    """

    # Default weights — tunable per brand via configuration
    SEMANTIC_WEIGHT: float = 0.60
    PERSONALISATION_WEIGHT: float = 0.25
    FRESHNESS_WEIGHT: float = 0.15

    # Personalisation boost factors
    BROWSED_BOOST: float = 0.10
    PURCHASED_BOOST: float = 0.15
    PREFERENCE_BOOST: float = 0.20

    @classmethod
    def compute_relevance_score(
        cls,
        semantic_score: float,
        personalisation_score: float = 0.0,
        freshness_score: float = 0.0,
    ) -> float:
        """
        Compute a composite relevance score from individual signals.

        All input scores should be normalised to [0.0, 1.0].
        Returns a score in [0.0, 1.0].
        """
        raw = (
            cls.SEMANTIC_WEIGHT * _clamp(semantic_score)
            + cls.PERSONALISATION_WEIGHT * _clamp(personalisation_score)
            + cls.FRESHNESS_WEIGHT * _clamp(freshness_score)
        )
        return _clamp(raw)

    @classmethod
    def apply_personalisation(
        cls,
        results: list[SearchResult],
        signals: ReRankingSignals,
    ) -> list[SearchResult]:
        """
        Re-rank search results based on personalisation signals.

        Boosts are additive and capped to prevent personalisation from
        completely overriding semantic relevance. Results are re-sorted
        by adjusted score and re-ranked sequentially.
        """
        if not signals.has_history and not signals.has_preferences:
            return results

        adjusted: list[SearchResult] = []
        for result in results:
            boost = _compute_personalisation_boost(result, signals)
            new_score = _clamp(result.score + boost)
            adjusted.append(replace(result, score=new_score))

        # Re-sort by adjusted score descending, then re-assign ranks
        adjusted.sort(key=lambda r: r.score, reverse=True)
        return [
            replace(r, rank=idx + 1)
            for idx, r in enumerate(adjusted)
        ]


def _compute_personalisation_boost(
    result: SearchResult,
    signals: ReRankingSignals,
) -> float:
    """
    Compute a personalisation boost for a single result.

    Boosts are cumulative but capped at the maximum personalisation weight
    to prevent any single result from being boosted disproportionately.
    """
    boost = 0.0

    if result.product_id in signals.browsing_history:
        boost += RankingService.BROWSED_BOOST

    if result.product_id in signals.purchase_history:
        # Penalise already-purchased items slightly — luxury customers
        # rarely buy the same item twice, but browsing indicates interest
        # in similar items, so we give a smaller boost than browsing.
        boost += RankingService.PURCHASED_BOOST * 0.5

    if signals.has_preferences:
        # Apply preference boost — in a full implementation this would
        # check product attributes against customer preferences.
        boost += RankingService.PREFERENCE_BOOST * _preference_match_score(
            result, signals
        )

    return min(boost, RankingService.PERSONALISATION_WEIGHT)


def _preference_match_score(
    result: SearchResult,
    signals: ReRankingSignals,
) -> float:
    """
    Score how well a product matches customer preferences.

    This is a simplified implementation. In production, the product
    attributes would be fetched and compared against the preference
    dictionary (preferred materials, colours, designers, etc.).
    """
    # Simplified: return a base match score when preferences exist.
    # Full implementation would compare product metadata against
    # signals.preferences keys and values.
    if signals.has_preferences:
        return 0.5
    return 0.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp a value to the given range."""
    return max(low, min(high, value))
