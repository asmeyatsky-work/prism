"""
Discovery DTOs — Pydantic models for structured search I/O.

Architectural Intent:
- Pydantic models serve as the contract between application and presentation layers
- Validated input (SearchRequestDTO) prevents invalid queries from reaching the domain
- Structured output (SearchResponseDTO) is compatible with AI structured output schemas
- FacetDTO provides a serialisation-ready view of domain Facet value objects
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequestDTO(BaseModel):
    """Input DTO for search execution."""

    tenant_id: str
    query_text: str | None = None
    image_uri: str | None = None
    modality: str = "TEXT"
    filters: dict[str, str | list[str]] = Field(default_factory=dict)
    locale: str = "en"
    top_k: int = Field(default=20, ge=1, le=100)
    customer_id: str | None = None
    session_id: str | None = None
    text_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    image_weight: float = Field(default=0.5, ge=0.0, le=1.0)


class SearchResultDTO(BaseModel):
    """A single search result in the response."""

    product_id: str
    score: float
    rank: int
    explanation: str = ""


class FacetValueDTO(BaseModel):
    """A single facet value."""

    value: str
    count: int
    selected: bool = False


class FacetDTO(BaseModel):
    """A facet dimension with its available values."""

    name: str
    display_name: str
    values: list[FacetValueDTO] = Field(default_factory=list)


class SearchResponseDTO(BaseModel):
    """Output DTO for search execution results."""

    session_id: str
    results: list[SearchResultDTO] = Field(default_factory=list)
    total_count: int = 0
    query_time_ms: float = 0.0
    modality: str = "TEXT"
    facets: list[FacetDTO] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return len(self.results) == 0


class SearchAnalyticsDTO(BaseModel):
    """Analytics summary for a search session."""

    session_id: str
    tenant_id: str
    query_count: int = 0
    total_results_served: int = 0
    total_clicks: int = 0
    engagement_rate: float = 0.0
    modalities_used: list[str] = Field(default_factory=list)
