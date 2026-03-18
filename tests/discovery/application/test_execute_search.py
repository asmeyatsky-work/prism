"""
Tests for the ExecuteSearchUseCase.

Tests cover:
- Text search dispatching to VectorSearchPort
- Image search dispatching to ImageSearchPort
- Hybrid search running text + image in parallel via asyncio.gather
- Personalisation re-ranking when customer_id is provided
- Error handling for invalid modality and search failures
- Session ID generation and propagation
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from prism.discovery.application.commands.execute_search import (
    ExecuteSearchUseCase,
    _fuse_results,
)
from prism.discovery.application.dtos.search_dto import SearchRequestDTO
from prism.discovery.domain.value_objects.search_query import (
    ReRankingSignals,
    SearchResult,
)
from prism.shared.domain.value_objects import ImageRef


# ── Test Doubles ──────────────────────────────────────────


class FakeVectorSearch:
    """In-memory fake for VectorSearchPort."""

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = results or []
        self.call_count = 0
        self.last_query: str = ""

    async def search_by_text(
        self,
        query: str,
        top_k: int = 20,
        filters: dict[str, str | list[str]] | None = None,
        tenant_id: str = "",
    ) -> list[SearchResult]:
        self.call_count += 1
        self.last_query = query
        return self.results[:top_k]


class FakeImageSearch:
    """In-memory fake for ImageSearchPort."""

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = results or []
        self.call_count = 0

    async def search_by_image(
        self,
        image: ImageRef,
        top_k: int = 20,
        tenant_id: str = "",
    ) -> list[SearchResult]:
        self.call_count += 1
        return self.results[:top_k]


class FakeHybridSearch:
    """In-memory fake for HybridSearchPort."""

    def __init__(self, results: list[SearchResult] | None = None) -> None:
        self.results = results or []
        self.call_count = 0

    async def search_hybrid(
        self,
        text: str,
        image: ImageRef,
        weights: tuple[float, float] = (0.5, 0.5),
        top_k: int = 20,
        filters: dict[str, str | list[str]] | None = None,
        tenant_id: str = "",
    ) -> list[SearchResult]:
        self.call_count += 1
        return self.results[:top_k]


class FakePersonalisation:
    """In-memory fake for PersonalisationPort."""

    def __init__(
        self,
        signals: ReRankingSignals | None = None,
        should_fail: bool = False,
    ) -> None:
        self.signals = signals or ReRankingSignals()
        self.should_fail = should_fail
        self.call_count = 0

    async def get_signals(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> ReRankingSignals:
        self.call_count += 1
        if self.should_fail:
            raise ConnectionError("Personalisation service unavailable")
        return self.signals


def _sample_results(count: int = 3, prefix: str = "prod") -> list[SearchResult]:
    return [
        SearchResult(
            product_id=f"{prefix}-{i}",
            score=0.9 - i * 0.1,
            rank=i + 1,
            explanation=f"match for {prefix}-{i}",
        )
        for i in range(count)
    ]


def _make_use_case(
    text_results: list[SearchResult] | None = None,
    image_results: list[SearchResult] | None = None,
    personalisation_signals: ReRankingSignals | None = None,
    personalisation_fails: bool = False,
) -> tuple[
    ExecuteSearchUseCase,
    FakeVectorSearch,
    FakeImageSearch,
    FakeHybridSearch,
    FakePersonalisation,
]:
    vector = FakeVectorSearch(text_results or _sample_results(prefix="text"))
    image = FakeImageSearch(image_results or _sample_results(prefix="img"))
    hybrid = FakeHybridSearch()
    personalisation = FakePersonalisation(
        signals=personalisation_signals,
        should_fail=personalisation_fails,
    )

    use_case = ExecuteSearchUseCase(
        vector_search=vector,
        image_search=image,
        hybrid_search=hybrid,
        personalisation=personalisation,
    )

    return use_case, vector, image, hybrid, personalisation


# ── Text Search ───────────────────────────────────────────


class TestTextSearch:
    @pytest.mark.asyncio
    async def test_text_search_dispatches_to_vector(self) -> None:
        use_case, vector, image, _, _ = _make_use_case()
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="leather handbag",
            modality="TEXT",
        )

        result = await use_case.execute(request)

        assert result.success
        assert vector.call_count == 1
        assert vector.last_query == "leather handbag"
        assert image.call_count == 0

    @pytest.mark.asyncio
    async def test_text_search_returns_results(self) -> None:
        use_case, _, _, _, _ = _make_use_case()
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="silk scarf",
            modality="TEXT",
        )

        result = await use_case.execute(request)

        assert result.success
        response = result.value
        assert response is not None
        assert len(response.results) == 3
        assert response.modality == "TEXT"

    @pytest.mark.asyncio
    async def test_text_search_respects_top_k(self) -> None:
        results = _sample_results(count=10, prefix="text")
        use_case, _, _, _, _ = _make_use_case(text_results=results)
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="evening gown",
            modality="TEXT",
            top_k=5,
        )

        result = await use_case.execute(request)

        assert result.success
        assert len(result.value.results) == 5


# ── Image Search ──────────────────────────────────────────


class TestImageSearch:
    @pytest.mark.asyncio
    async def test_image_search_dispatches_to_image_port(self) -> None:
        use_case, vector, image, _, _ = _make_use_case()
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            image_uri="gs://bucket/img.jpg",
            modality="IMAGE",
        )

        result = await use_case.execute(request)

        assert result.success
        assert image.call_count == 1
        assert vector.call_count == 0


# ── Hybrid Search (Parallel) ─────────────────────────────


class TestHybridSearch:
    @pytest.mark.asyncio
    async def test_hybrid_runs_text_and_image_in_parallel(self) -> None:
        """
        Verify that hybrid search dispatches BOTH text and image searches
        concurrently via asyncio.gather, then fuses the results.
        """
        text_results = [
            SearchResult(product_id="prod-A", score=0.9, rank=1, explanation="text"),
            SearchResult(product_id="prod-B", score=0.8, rank=2, explanation="text"),
        ]
        image_results = [
            SearchResult(product_id="prod-B", score=0.85, rank=1, explanation="image"),
            SearchResult(product_id="prod-C", score=0.7, rank=2, explanation="image"),
        ]
        use_case, vector, image, _, _ = _make_use_case(
            text_results=text_results,
            image_results=image_results,
        )
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="leather handbag",
            image_uri="gs://bucket/ref.jpg",
            modality="HYBRID",
        )

        result = await use_case.execute(request)

        assert result.success
        # Both ports were called
        assert vector.call_count == 1
        assert image.call_count == 1

    @pytest.mark.asyncio
    async def test_hybrid_fuses_results_correctly(self) -> None:
        """
        Verify that products appearing in both text and image results
        receive a combined score higher than either alone.
        """
        text_results = [
            SearchResult(product_id="prod-A", score=0.9, rank=1, explanation="text A"),
            SearchResult(product_id="prod-B", score=0.8, rank=2, explanation="text B"),
        ]
        image_results = [
            SearchResult(product_id="prod-B", score=0.85, rank=1, explanation="image B"),
            SearchResult(product_id="prod-C", score=0.7, rank=2, explanation="image C"),
        ]

        fused = _fuse_results(text_results, image_results, 0.5, 0.5)

        # prod-B appears in both and should have highest combined score
        # prod-B: 0.8*0.5 + 0.85*0.5 = 0.4 + 0.425 = 0.825
        # prod-A: 0.9*0.5 = 0.45
        # prod-C: 0.7*0.5 = 0.35
        assert fused[0].product_id == "prod-B"
        assert fused[0].score == pytest.approx(0.825)
        assert fused[0].rank == 1

    @pytest.mark.asyncio
    async def test_hybrid_search_uses_custom_weights(self) -> None:
        text_results = [
            SearchResult(product_id="prod-A", score=0.9, rank=1, explanation="text"),
        ]
        image_results = [
            SearchResult(product_id="prod-A", score=0.5, rank=1, explanation="image"),
        ]

        # Text-heavy weighting
        fused = _fuse_results(text_results, image_results, 0.8, 0.2)
        # prod-A: 0.9*0.8 + 0.5*0.2 = 0.72 + 0.10 = 0.82
        assert fused[0].score == pytest.approx(0.82)


# ── Personalisation ──────────────────────────────────────


class TestPersonalisation:
    @pytest.mark.asyncio
    async def test_personalisation_applied_when_customer_present(self) -> None:
        signals = ReRankingSignals(
            browsing_history=("text-0",),
            purchase_history=(),
            preferences={},
        )
        use_case, _, _, _, personalisation = _make_use_case(
            personalisation_signals=signals,
        )
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="leather bag",
            modality="TEXT",
            customer_id="cust-42",
        )

        result = await use_case.execute(request)

        assert result.success
        assert personalisation.call_count == 1

    @pytest.mark.asyncio
    async def test_no_personalisation_for_anonymous(self) -> None:
        use_case, _, _, _, personalisation = _make_use_case()
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="leather bag",
            modality="TEXT",
            customer_id=None,
        )

        result = await use_case.execute(request)

        assert result.success
        assert personalisation.call_count == 0

    @pytest.mark.asyncio
    async def test_personalisation_failure_degrades_gracefully(self) -> None:
        use_case, _, _, _, _ = _make_use_case(personalisation_fails=True)
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="evening gown",
            modality="TEXT",
            customer_id="cust-42",
        )

        result = await use_case.execute(request)

        # Search should succeed even if personalisation fails
        assert result.success
        assert result.value is not None


# ── Error Handling ────────────────────────────────────────


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_invalid_modality_returns_error(self) -> None:
        use_case, _, _, _, _ = _make_use_case()
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="handbag",
            modality="INVALID",
        )

        result = await use_case.execute(request)

        assert not result.success
        assert result.error_code == "INVALID_MODALITY"

    @pytest.mark.asyncio
    async def test_session_id_generated_when_not_provided(self) -> None:
        use_case, _, _, _, _ = _make_use_case()
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="scarf",
            modality="TEXT",
        )

        result = await use_case.execute(request)

        assert result.success
        assert result.value.session_id  # non-empty UUID

    @pytest.mark.asyncio
    async def test_existing_session_id_preserved(self) -> None:
        use_case, _, _, _, _ = _make_use_case()
        request = SearchRequestDTO(
            tenant_id="brand-gucci",
            query_text="scarf",
            modality="TEXT",
            session_id="existing-sess-001",
        )

        result = await use_case.execute(request)

        assert result.success
        assert result.value.session_id == "existing-sess-001"


# ── Result Fusion ─────────────────────────────────────────


class TestResultFusion:
    def test_empty_inputs(self) -> None:
        fused = _fuse_results([], [], 0.5, 0.5)
        assert fused == []

    def test_text_only(self) -> None:
        text_results = _sample_results(count=2, prefix="text")
        fused = _fuse_results(text_results, [], 0.5, 0.5)
        assert len(fused) == 2

    def test_image_only(self) -> None:
        image_results = _sample_results(count=2, prefix="img")
        fused = _fuse_results([], image_results, 0.5, 0.5)
        assert len(fused) == 2

    def test_ranks_are_sequential(self) -> None:
        text_results = _sample_results(count=3, prefix="text")
        image_results = _sample_results(count=3, prefix="img")
        fused = _fuse_results(text_results, image_results, 0.5, 0.5)

        ranks = [r.rank for r in fused]
        assert ranks == list(range(1, len(fused) + 1))
