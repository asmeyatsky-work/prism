"""
Commerce Domain Service — Event Processing

Architectural Intent:
- Stateless domain service for commerce event classification and transformation
- classify_event maps UCP event type strings to CommerceEventType enum values
- should_retry implements retry eligibility logic as a pure domain rule
- transform_to_pces converts UCP events to PRISM Commerce Event Schema (PCES)
- No infrastructure dependencies — operates purely on domain types

Classification Rules:
  "product.created"   -> PRODUCT_CREATED
  "product.updated"   -> PRODUCT_UPDATED
  "inventory.changed" -> INVENTORY_CHANGED
  "price.changed"     -> PRICE_CHANGED
  "order.placed"      -> ORDER_PLACED
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from prism.commerce.domain.entities.commerce_event import (
    CommerceEvent,
    CommerceEventType,
    ProcessingStatus,
)
from prism.commerce.domain.value_objects.ucp_schema import (
    PRISMCommerceEventSchema,
    UCPEventEnvelope,
    UCPProductRecord,
)
from prism.shared.domain.value_objects import Currency, Money

# Mapping from UCP event type strings to domain event types.
# Supports both dot-notation (UCP native) and underscore (normalised) formats.
_EVENT_TYPE_MAP: dict[str, CommerceEventType] = {
    "product.created": CommerceEventType.PRODUCT_CREATED,
    "product_created": CommerceEventType.PRODUCT_CREATED,
    "product.updated": CommerceEventType.PRODUCT_UPDATED,
    "product_updated": CommerceEventType.PRODUCT_UPDATED,
    "inventory.changed": CommerceEventType.INVENTORY_CHANGED,
    "inventory_changed": CommerceEventType.INVENTORY_CHANGED,
    "price.changed": CommerceEventType.PRICE_CHANGED,
    "price_changed": CommerceEventType.PRICE_CHANGED,
    "order.placed": CommerceEventType.ORDER_PLACED,
    "order_placed": CommerceEventType.ORDER_PLACED,
}


class EventProcessingService:
    """
    Stateless domain service for commerce event processing logic.

    All methods are pure functions operating on domain types with no
    infrastructure dependencies. This service encodes business rules
    for event classification, retry eligibility, and schema transformation.
    """

    @staticmethod
    def classify_event(envelope: UCPEventEnvelope) -> CommerceEventType:
        """
        Classify a UCP event envelope into a CommerceEventType.

        Normalises the event type string to lowercase and looks up the mapping.
        Defaults to PRODUCT_UPDATED for unrecognised event types to avoid
        data loss in the pipeline.

        Args:
            envelope: The inbound UCP event envelope.

        Returns:
            The classified CommerceEventType.
        """
        normalised = envelope.event_type.lower().strip()
        return _EVENT_TYPE_MAP.get(normalised, CommerceEventType.PRODUCT_UPDATED)

    @staticmethod
    def should_retry(event: CommerceEvent) -> bool:
        """
        Determine whether a failed commerce event should be retried.

        Retry is permitted when:
        - The event is in FAILED status
        - The retry count has not exceeded the maximum (defined on the entity)

        Args:
            event: The commerce event to evaluate.

        Returns:
            True if the event is eligible for retry.
        """
        return event.can_retry

    @staticmethod
    def transform_to_pces(
        ucp_event: UCPEventEnvelope,
        enrichment_data: dict[str, Any],
    ) -> PRISMCommerceEventSchema:
        """
        Transform a UCP event and enrichment data into a PRISM Commerce Event Schema.

        Extracts product data from the UCP event payload and merges it with
        AI enrichment results to produce the canonical PCES format.

        Args:
            ucp_event: The original UCP event envelope.
            enrichment_data: AI enrichment results (attributes, taxonomy, scores).

        Returns:
            A PRISMCommerceEventSchema value object ready for feed publishing.
        """
        payload = ucp_event.payload_dict

        # Build price if available in payload
        price: Money | None = None
        raw_price = payload.get("price")
        raw_currency = payload.get("currency", "USD")
        if raw_price is not None:
            try:
                currency = Currency(raw_currency)
            except ValueError:
                currency = Currency.USD
            price = Money(amount=float(raw_price), currency=currency)

        # Build raw attributes from payload
        raw_attrs = payload.get("attributes", {})
        attr_tuple: tuple[tuple[str, str], ...] = ()
        if isinstance(raw_attrs, dict):
            attr_tuple = tuple(
                (str(k), str(v)) for k, v in raw_attrs.items()
            )

        # Build images tuple
        raw_images = payload.get("images", [])
        images_tuple: tuple[str, ...] = ()
        if isinstance(raw_images, (list, tuple)):
            images_tuple = tuple(str(img) for img in raw_images)

        # Construct UCP product record
        ucp_product = UCPProductRecord(
            id=payload.get("id", ucp_event.event_id),
            sku=payload.get("sku", payload.get("id", ucp_event.event_id)),
            name=payload.get("name", ""),
            brand=payload.get("brand", ""),
            price=price,
            currency=Currency(raw_currency) if raw_currency in Currency.__members__ else Currency.USD,
            images=images_tuple,
            attributes=attr_tuple,
            inventory_status=payload.get("inventory_status", ""),
        )

        # Extract enrichment fields
        enriched_attrs = enrichment_data.get("enriched_attributes", {})
        enriched_tuple: tuple[tuple[str, str], ...] = ()
        if isinstance(enriched_attrs, dict):
            enriched_tuple = tuple(
                (str(k), str(v)) for k, v in enriched_attrs.items()
            )

        confidence_raw = enrichment_data.get("confidence_scores", {})
        confidence_tuple: tuple[tuple[str, float], ...] = ()
        if isinstance(confidence_raw, dict):
            confidence_tuple = tuple(
                (str(k), float(v)) for k, v in confidence_raw.items()
            )

        taxonomy_raw = enrichment_data.get("taxonomy_codes", [])
        taxonomy_codes: tuple[str, ...] = ()
        if isinstance(taxonomy_raw, (list, tuple)):
            taxonomy_codes = tuple(str(code) for code in taxonomy_raw)

        discovery_raw = enrichment_data.get("discovery_signals", {})
        discovery_tuple: tuple[tuple[str, Any], ...] = ()
        if isinstance(discovery_raw, dict):
            discovery_tuple = tuple(discovery_raw.items())

        return PRISMCommerceEventSchema(
            ucp_product=ucp_product,
            enrichment_version=enrichment_data.get("enrichment_version", "1.0"),
            enriched_attributes=enriched_tuple,
            quality_score=float(enrichment_data.get("quality_score", 0.0)),
            discovery_signals=discovery_tuple,
            taxonomy_codes=taxonomy_codes,
            enrichment_timestamp=datetime.now(UTC),
            enrichment_model=enrichment_data.get("enrichment_model", ""),
            confidence_scores=confidence_tuple,
        )
