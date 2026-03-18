"""
Commerce Application DTOs — Data Transfer Objects

Architectural Intent:
- Pydantic models for structured data at the application boundary
- UCPEventDTO represents inbound UCP event data from API/Pub/Sub
- InventoryDTO represents inventory query results
- FeedStatusDTO represents Google Shopping feed status
- DTOs decouple domain internals from external representations
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UCPEventDTO(BaseModel):
    """
    Data transfer object for inbound UCP events.

    Used at the application boundary to accept raw UCP event data
    before it is converted to domain types.
    """

    event_id: str = ""
    event_type: str = ""
    timestamp: datetime | None = None
    source: str = "UCP"
    payload: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""

    class Config:
        frozen = True


class InventoryDTO(BaseModel):
    """
    Data transfer object for inventory query results.

    Presents inventory availability information in a flat,
    serialisation-friendly format.
    """

    product_id: str = ""
    tenant_id: str = ""
    available_quantity: int = 0
    location: str = ""
    fulfilment_options: list[str] = Field(default_factory=list)
    is_in_stock: bool = False
    last_updated: datetime | None = None

    class Config:
        frozen = True


class FeedStatusDTO(BaseModel):
    """
    Data transfer object for Google Shopping feed status queries.

    Presents feed synchronisation state and quality metrics.
    """

    feed_id: str = ""
    tenant_id: str = ""
    product_count: int = 0
    sync_status: str = ""
    quality_score: float = 0.0
    last_sync: datetime | None = None

    class Config:
        frozen = True
