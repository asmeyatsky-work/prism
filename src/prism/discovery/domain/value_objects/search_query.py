"""
Discovery Value Objects — Search queries, results, and re-ranking signals.

Architectural Intent:
- Immutable value objects for the search domain
- SearchQuery supports multimodal input (text, image, hybrid, voice)
- SearchResult carries explanation for transparency in luxury retail
- ReRankingSignals capture personalisation context for score adjustment
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from prism.shared.domain.value_objects import ImageRef, Locale, ValueObject


class SearchModality(str, Enum):
    """Supported search input modalities."""

    TEXT = "TEXT"
    IMAGE = "IMAGE"
    HYBRID = "HYBRID"
    VOICE = "VOICE"


@dataclass(frozen=True)
class SearchQuery(ValueObject):
    """
    A multimodal search query.

    Luxury retail searches may combine text descriptions with reference
    images — for example, a customer photographing a handbag seen in a
    magazine and adding 'in navy blue leather'.
    """

    text: str | None = None
    image: ImageRef | None = None
    modality: SearchModality = SearchModality.TEXT
    filters: dict[str, str | list[str]] = field(default_factory=dict)
    locale: Locale = field(default_factory=lambda: Locale(language="en"))

    def __post_init__(self) -> None:
        if self.modality == SearchModality.TEXT and not self.text:
            raise ValueError("Text modality requires a text query")
        if self.modality == SearchModality.IMAGE and not self.image:
            raise ValueError("Image modality requires an image reference")
        if self.modality == SearchModality.HYBRID and not (self.text and self.image):
            raise ValueError(
                "Hybrid modality requires both text and image"
            )


@dataclass(frozen=True)
class SearchResult(ValueObject):
    """
    A single search result with relevance metadata.

    The explanation field provides human-readable reasoning for the
    ranking — important for luxury clienteling where advisors need
    to articulate why a product was recommended.
    """

    product_id: str = ""
    score: float = 0.0
    rank: int = 0
    explanation: str = ""


@dataclass(frozen=True)
class SearchResultSet(ValueObject):
    """
    A complete set of search results for a single query execution.

    Carries timing and type metadata for analytics and SLA monitoring.
    """

    results: tuple[SearchResult, ...] = ()
    total_count: int = 0
    query_time_ms: float = 0.0
    search_type: SearchModality = SearchModality.TEXT

    @property
    def is_empty(self) -> bool:
        return len(self.results) == 0

    @property
    def top_result(self) -> SearchResult | None:
        return self.results[0] if self.results else None


@dataclass(frozen=True)
class ReRankingSignals(ValueObject):
    """
    Personalisation signals used to re-rank search results.

    Captures a customer's browsing and purchase history along with
    explicit preferences (e.g., preferred materials, colours, designers).
    """

    browsing_history: tuple[str, ...] = ()
    purchase_history: tuple[str, ...] = ()
    preferences: dict[str, str | list[str]] = field(default_factory=dict)

    @property
    def has_history(self) -> bool:
        return bool(self.browsing_history or self.purchase_history)

    @property
    def has_preferences(self) -> bool:
        return bool(self.preferences)
