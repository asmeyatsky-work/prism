"""
Discovery Command — Execute Search Use Case.

Architectural Intent:
- Orchestrates multimodal search across text, image, and hybrid modalities
- For hybrid search: runs text and image searches in parallel via asyncio.gather,
  then fuses results using score-weighted rank fusion
- Applies personalisation re-ranking when customer context is available
- Produces domain events on the SearchSession aggregate for downstream consumption

Parallelism-First Design:
- Text and image vector searches are I/O-bound operations (network calls to
  Vertex AI Vector Search). Running them concurrently halves hybrid search latency.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import replace
from uuid import uuid4

from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import DomainEvent

from prism.discovery.application.dtos.search_dto import (
    SearchRequestDTO,
    SearchResponseDTO,
    SearchResultDTO,
)
from prism.discovery.domain.entities.search_session import SearchSession
from prism.discovery.domain.events.discovery_events import SearchExecutedEvent
from prism.discovery.domain.ports.search_ports import (
    HybridSearchPort,
    ImageSearchPort,
    PersonalisationPort,
    VectorSearchPort,
)
from prism.discovery.domain.services.ranking_service import RankingService
from prism.discovery.domain.value_objects.search_query import (
    ReRankingSignals,
    SearchModality,
    SearchQuery,
    SearchResult,
    SearchResultSet,
)
from prism.shared.domain.value_objects import ImageRef, Locale

logger = logging.getLogger(__name__)


class ExecuteSearchUseCase:
    """
    Application use case for executing multimodal searches.

    Coordinates domain objects, infrastructure ports, and domain services
    to fulfil a search request. Returns a CommandResult wrapping the
    SearchResponseDTO on success or an error on failure.
    """

    def __init__(
        self,
        vector_search: VectorSearchPort,
        image_search: ImageSearchPort,
        hybrid_search: HybridSearchPort,
        personalisation: PersonalisationPort,
        event_publisher: _EventPublisher | None = None,
    ) -> None:
        self._vector_search = vector_search
        self._image_search = image_search
        self._hybrid_search = hybrid_search
        self._personalisation = personalisation
        self._event_publisher = event_publisher

    async def execute(
        self,
        request: SearchRequestDTO,
    ) -> CommandResult[SearchResponseDTO]:
        """Execute a search and return results."""
        start = time.monotonic()

        try:
            modality = SearchModality(request.modality)
        except ValueError:
            return CommandResult.fail(
                error=f"Invalid search modality: {request.modality}",
                code="INVALID_MODALITY",
            )

        session_id = request.session_id or str(uuid4())
        session = SearchSession(
            session_id=session_id,
            tenant_id=request.tenant_id,
            customer_id=request.customer_id,
        )

        try:
            results = await self._dispatch_search(request, modality)
        except Exception as exc:
            logger.exception("Search execution failed for session %s", session_id)
            return CommandResult.fail(
                error=f"Search failed: {exc}",
                code="SEARCH_EXECUTION_ERROR",
            )

        # Apply personalisation re-ranking if customer context is available
        if request.customer_id:
            results = await self._apply_personalisation(
                results, request.customer_id, request.tenant_id
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Build domain value objects
        search_results = tuple(
            SearchResult(
                product_id=r.product_id,
                score=r.score,
                rank=r.rank,
                explanation=r.explanation,
            )
            for r in results
        )
        result_set = SearchResultSet(
            results=search_results,
            total_count=len(search_results),
            query_time_ms=elapsed_ms,
            search_type=modality,
        )

        # Build the SearchQuery value object
        image_ref = (
            _parse_image_ref(request.image_uri)
            if request.image_uri
            else None
        )
        locale = Locale(language=request.locale)
        query = SearchQuery(
            text=request.query_text,
            image=image_ref,
            modality=modality,
            filters=request.filters,
            locale=locale,
        )

        # Update the aggregate — collects domain events
        session = session.add_query(query, result_set)

        # Publish domain events
        if self._event_publisher and session.domain_events:
            await self._event_publisher.publish(list(session.domain_events))
            session = session.clear_events()

        # Build response DTO
        response = SearchResponseDTO(
            session_id=session_id,
            results=[
                SearchResultDTO(
                    product_id=r.product_id,
                    score=r.score,
                    rank=r.rank,
                    explanation=r.explanation,
                )
                for r in search_results
            ],
            total_count=result_set.total_count,
            query_time_ms=elapsed_ms,
            modality=modality.value,
        )

        return CommandResult.ok(response)

    async def _dispatch_search(
        self,
        request: SearchRequestDTO,
        modality: SearchModality,
    ) -> list[SearchResult]:
        """Route to the appropriate search backend based on modality."""
        if modality == SearchModality.TEXT:
            return await self._vector_search.search_by_text(
                query=request.query_text or "",
                top_k=request.top_k,
                filters=request.filters or None,
                tenant_id=request.tenant_id,
            )

        if modality == SearchModality.IMAGE:
            image_ref = _parse_image_ref(request.image_uri or "")
            return await self._image_search.search_by_image(
                image=image_ref,
                top_k=request.top_k,
                tenant_id=request.tenant_id,
            )

        if modality in (SearchModality.HYBRID, SearchModality.VOICE):
            return await self._execute_hybrid_search(request)

        return []

    async def _execute_hybrid_search(
        self,
        request: SearchRequestDTO,
    ) -> list[SearchResult]:
        """
        Execute hybrid search by running text and image searches in parallel,
        then fusing results via score-weighted rank fusion.

        This is the parallelism-first pattern: both searches are I/O-bound
        calls to vector search infrastructure. Running them concurrently
        halves the wall-clock time compared to sequential execution.
        """
        image_ref = _parse_image_ref(request.image_uri or "")
        text_query = request.query_text or ""

        # Run text and image searches in parallel
        text_results, image_results = await asyncio.gather(
            self._vector_search.search_by_text(
                query=text_query,
                top_k=request.top_k,
                filters=request.filters or None,
                tenant_id=request.tenant_id,
            ),
            self._image_search.search_by_image(
                image=image_ref,
                top_k=request.top_k,
                tenant_id=request.tenant_id,
            ),
        )

        # Fuse results using score-weighted combination
        return _fuse_results(
            text_results=text_results,
            image_results=image_results,
            text_weight=request.text_weight,
            image_weight=request.image_weight,
        )

    async def _apply_personalisation(
        self,
        results: list[SearchResult],
        customer_id: str,
        tenant_id: str,
    ) -> list[SearchResult]:
        """Fetch personalisation signals and re-rank results."""
        try:
            signals = await self._personalisation.get_signals(
                customer_id=customer_id,
                tenant_id=tenant_id,
            )
            return RankingService.apply_personalisation(results, signals)
        except Exception:
            logger.warning(
                "Personalisation failed for customer %s — returning unranked results",
                customer_id,
            )
            return results


def _fuse_results(
    text_results: list[SearchResult],
    image_results: list[SearchResult],
    text_weight: float = 0.5,
    image_weight: float = 0.5,
) -> list[SearchResult]:
    """
    Fuse text and image search results using weighted score combination.

    Products appearing in both result sets receive a combined score.
    Products appearing in only one set receive a discounted score.
    """
    scores: dict[str, tuple[float, str]] = {}

    for r in text_results:
        weighted = r.score * text_weight
        scores[r.product_id] = (weighted, r.explanation)

    for r in image_results:
        weighted = r.score * image_weight
        if r.product_id in scores:
            existing_score, existing_explanation = scores[r.product_id]
            combined = existing_score + weighted
            explanation = f"{existing_explanation}; visual match: {r.explanation}"
            scores[r.product_id] = (combined, explanation)
        else:
            scores[r.product_id] = (weighted, f"visual match: {r.explanation}")

    # Sort by fused score descending and assign ranks
    sorted_items = sorted(scores.items(), key=lambda x: x[1][0], reverse=True)
    return [
        SearchResult(
            product_id=pid,
            score=score,
            rank=idx + 1,
            explanation=explanation,
        )
        for idx, (pid, (score, explanation)) in enumerate(sorted_items)
    ]


def _parse_image_ref(uri: str) -> ImageRef:
    """
    Parse a GCS URI or simple path into an ImageRef value object.

    Supports gs://bucket/path format and plain path strings.
    """
    if uri.startswith("gs://"):
        parts = uri[5:].split("/", 1)
        bucket = parts[0]
        path = parts[1] if len(parts) > 1 else ""
        return ImageRef(bucket=bucket, path=path)
    return ImageRef(bucket="default", path=uri)


class _EventPublisher:
    """Protocol-compatible event publisher interface."""

    async def publish(self, events: list[DomainEvent]) -> None: ...
