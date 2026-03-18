"""
Try-On Domain Service — Validation

Architectural Intent:
- Pure domain service with no infrastructure dependencies
- Encapsulates try-on business rules that don't belong on a single entity
- Validates product category eligibility and latency budget compliance
- Stateless — all inputs are passed explicitly
"""

from __future__ import annotations

from enum import Enum


class TryOnCategory(str, Enum):
    """Product categories supported by the virtual try-on engine."""

    APPAREL = "APPAREL"
    ACCESSORIES = "ACCESSORIES"
    EYEWEAR = "EYEWEAR"
    JEWELLERY = "JEWELLERY"


# Default set of supported categories
DEFAULT_SUPPORTED_CATEGORIES: frozenset[TryOnCategory] = frozenset(TryOnCategory)

# P95 latency target in milliseconds (4 seconds per spec)
DEFAULT_P95_TARGET_MS: int = 4000


class TryOnValidationService:
    """
    Domain service for try-on validation rules.

    Stateless — instantiate once and reuse. No infrastructure coupling.
    """

    @staticmethod
    def validate_product_category(
        product_category: str,
        supported_categories: frozenset[TryOnCategory] | None = None,
    ) -> bool:
        """
        Check whether a product category is eligible for virtual try-on.

        Args:
            product_category: The category string from the product catalogue.
            supported_categories: Allowed categories. Defaults to all TryOnCategory values.

        Returns:
            True if the category is supported, False otherwise.
        """
        if supported_categories is None:
            supported_categories = DEFAULT_SUPPORTED_CATEGORIES

        try:
            category = TryOnCategory(product_category)
        except ValueError:
            return False

        return category in supported_categories

    @staticmethod
    def validate_latency_budget(
        processing_time_ms: int,
        target_p95_ms: int = DEFAULT_P95_TARGET_MS,
    ) -> bool:
        """
        Check whether a try-on processing time meets the P95 latency SLA.

        Args:
            processing_time_ms: Actual processing time in milliseconds.
            target_p95_ms: P95 latency target in milliseconds.

        Returns:
            True if the processing time is within budget, False otherwise.
        """
        if processing_time_ms < 0:
            raise ValueError("processing_time_ms cannot be negative")
        return processing_time_ms <= target_p95_ms
