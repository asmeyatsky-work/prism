"""
Commerce Value Objects — UCP Schema and PRISM Commerce Event Schema (PCES)

Architectural Intent:
- UCPProductRecord represents raw product data as received from the Unified Commerce Platform
- UCPEventEnvelope wraps every UCP event for routing and deduplication
- PRISMCommerceEventSchema (PCES) extends UCP data with AI enrichment metadata
  and discovery analytics — it is the canonical commerce data format within PRISM
- All value objects are frozen dataclasses — equality is structural, not identity-based

Data Flow:
  UCP -> UCPEventEnvelope -> classify -> UCPProductRecord -> enrich -> PCES -> Google Shopping / UCP
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from prism.shared.domain.value_objects import Currency, Money, ValueObject


@dataclass(frozen=True)
class UCPProductRecord(ValueObject):
    """
    Raw product data as received from the Unified Commerce Platform.

    Represents the source-of-truth product record before PRISM enrichment.
    All fields are optional beyond id/sku to support partial updates from UCP.

    Attributes:
        id: UCP-assigned product identifier.
        sku: Stock keeping unit — unique within a tenant.
        name: Product display name.
        brand: Brand name (e.g. "Gucci", "Hermès").
        price: Product price as a Money value object.
        currency: ISO 4217 currency code (redundant with price.currency for compatibility).
        images: Tuple of image URLs from UCP.
        attributes: Key-value product attributes (material, colour, etc.).
        inventory_status: UCP inventory status string (e.g. "IN_STOCK", "LOW_STOCK").
    """

    id: str = ""
    sku: str = ""
    name: str = ""
    brand: str = ""
    price: Money | None = None
    currency: Currency = Currency.USD
    images: tuple[str, ...] = ()
    attributes: tuple[tuple[str, str], ...] = ()
    inventory_status: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("UCPProductRecord.id cannot be empty")
        if not self.sku:
            raise ValueError("UCPProductRecord.sku cannot be empty")


@dataclass(frozen=True)
class UCPEventEnvelope(ValueObject):
    """
    Envelope wrapping every inbound UCP event for routing and deduplication.

    The envelope is immutable and carries the full event payload as a dict.
    Event classification is performed by the domain service, not the envelope itself.

    Attributes:
        event_id: Unique event identifier for idempotency.
        event_type: Raw event type string from UCP (e.g. "product.created").
        timestamp: When the event was produced at the UCP source.
        source: Origin system identifier.
        payload: Raw event payload as a dictionary.
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    source: str = ""
    payload: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.event_type:
            raise ValueError("UCPEventEnvelope.event_type cannot be empty")

    @property
    def payload_dict(self) -> dict[str, Any]:
        """Access payload as a mutable dict for downstream processing."""
        return dict(self.payload)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> UCPEventEnvelope:
        """Construct envelope from a raw dictionary (e.g. Pub/Sub message)."""
        payload = data.get("payload", {})
        payload_tuple = tuple(payload.items()) if isinstance(payload, dict) else ()
        return UCPEventEnvelope(
            event_id=data.get("event_id", str(uuid4())),
            event_type=data.get("event_type", ""),
            timestamp=data.get("timestamp", datetime.now(UTC)),
            source=data.get("source", ""),
            payload=payload_tuple,
        )


@dataclass(frozen=True)
class PRISMCommerceEventSchema(ValueObject):
    """
    PRISM Commerce Event Schema (PCES) — canonical enriched commerce data format.

    Extends UCP product data with AI enrichment metadata and discovery analytics.
    This is the schema pushed back to UCP and published to Google Shopping feeds.

    Attributes:
        ucp_product: The original UCP product record.
        enrichment_version: Version of the enrichment pipeline that produced this data.
        enriched_attributes: AI-generated attribute key-value pairs.
        quality_score: Overall data quality score (0.0 to 1.0).
        discovery_signals: Analytics signals for search/discovery optimisation.
        taxonomy_codes: PRISM taxonomy codes assigned by AI classification.
        enrichment_timestamp: When enrichment was performed.
        enrichment_model: AI model identifier used for enrichment.
        confidence_scores: Per-attribute confidence scores from AI enrichment.
    """

    ucp_product: UCPProductRecord | None = None
    enrichment_version: str = "1.0"
    enriched_attributes: tuple[tuple[str, str], ...] = ()
    quality_score: float = 0.0
    discovery_signals: tuple[tuple[str, Any], ...] = ()
    taxonomy_codes: tuple[str, ...] = ()
    enrichment_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    enrichment_model: str = ""
    confidence_scores: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError(
                f"quality_score must be between 0.0 and 1.0, got {self.quality_score}"
            )

    @property
    def enriched_attributes_dict(self) -> dict[str, str]:
        """Access enriched attributes as a mutable dict."""
        return dict(self.enriched_attributes)

    @property
    def confidence_scores_dict(self) -> dict[str, float]:
        """Access confidence scores as a mutable dict."""
        return dict(self.confidence_scores)

    def to_feed_dict(self) -> dict[str, Any]:
        """Serialise to a dict suitable for Google Shopping feed publishing."""
        product = self.ucp_product
        result: dict[str, Any] = {
            "enrichment_version": self.enrichment_version,
            "quality_score": self.quality_score,
            "taxonomy_codes": list(self.taxonomy_codes),
            "enriched_attributes": self.enriched_attributes_dict,
            "enrichment_model": self.enrichment_model,
        }
        if product is not None:
            result.update(
                {
                    "id": product.id,
                    "sku": product.sku,
                    "name": product.name,
                    "brand": product.brand,
                    "images": list(product.images),
                    "inventory_status": product.inventory_status,
                }
            )
            if product.price is not None:
                result["price"] = product.price.amount
                result["currency"] = product.price.currency.value
        return result
