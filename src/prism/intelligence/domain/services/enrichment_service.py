"""
Intelligence Domain Service — Enrichment Validation and Merging

Architectural Intent:
- Pure domain logic that does not belong to a single aggregate
- Stateless service — all inputs and outputs are explicit
- Confidence thresholds enforce quality gates in the enrichment pipeline
- Attribute merging preserves existing data when new extractions are partial
- Human review triggering prevents low-confidence AI outputs from auto-publishing
"""

from __future__ import annotations

from dataclasses import dataclass

# Default thresholds for luxury retail quality standards
_DEFAULT_CONFIDENCE_THRESHOLD = 0.75
_HUMAN_REVIEW_THRESHOLD = 0.6
_CRITICAL_ATTRIBUTES = ("material", "colour", "silhouette")


@dataclass(frozen=True)
class EnrichmentService:
    """
    Domain service for enrichment validation, merging, and quality gating.

    Encapsulates business rules that span multiple domain objects:
    - Confidence validation against configurable thresholds
    - Attribute merging with precedence rules
    - Human review triggering based on confidence analysis
    """

    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD
    human_review_threshold: float = _HUMAN_REVIEW_THRESHOLD
    critical_attributes: tuple[str, ...] = _CRITICAL_ATTRIBUTES

    def validate_extraction_confidence(
        self,
        attributes: dict[str, str],
        confidence_scores: dict[str, float],
        threshold: float | None = None,
    ) -> bool:
        """
        Validate that all extracted attributes meet the confidence threshold.

        Args:
            attributes: Extracted attribute name-value pairs.
            confidence_scores: Confidence score for each attribute.
            threshold: Optional override for the default confidence threshold.

        Returns:
            True if all attributes meet or exceed the threshold.
        """
        effective_threshold = threshold if threshold is not None else self.confidence_threshold
        return all(
            confidence_scores.get(attr, 0.0) >= effective_threshold
            for attr in attributes
        )

    def merge_attributes(
        self,
        existing: dict[str, str],
        extracted: dict[str, str],
        confidence_scores: dict[str, float] | None = None,
    ) -> dict[str, str]:
        """
        Merge newly extracted attributes with existing product attributes.

        Precedence rules:
        1. New attributes with confidence >= threshold overwrite existing values
        2. New attributes with confidence < threshold are discarded
        3. Existing attributes not present in extraction are preserved
        4. If no confidence_scores provided, all extracted values are accepted

        Args:
            existing: Current product attributes.
            extracted: Newly extracted attributes from AI.
            confidence_scores: Optional confidence scores for extracted attributes.

        Returns:
            Merged attribute dictionary.
        """
        merged = dict(existing)

        for attr, value in extracted.items():
            if not value or not value.strip():
                continue

            if confidence_scores is not None:
                score = confidence_scores.get(attr, 0.0)
                if score < self.confidence_threshold:
                    continue

            merged[attr] = value

        return merged

    def should_trigger_human_review(
        self,
        confidence_scores: dict[str, float],
    ) -> bool:
        """
        Determine whether an enrichment result requires human review.

        Human review is triggered when:
        1. Any critical attribute has confidence below the review threshold
        2. The average confidence across all attributes is below the review threshold
        3. Any attribute has zero confidence (extraction likely failed)

        Args:
            confidence_scores: Confidence scores keyed by attribute name.

        Returns:
            True if human review should be triggered.
        """
        if not confidence_scores:
            return True

        # Zero confidence on any attribute suggests extraction failure
        if any(score == 0.0 for score in confidence_scores.values()):
            return True

        # Critical attributes below threshold require review
        for attr in self.critical_attributes:
            if attr in confidence_scores:
                if confidence_scores[attr] < self.human_review_threshold:
                    return True

        # Low average confidence requires review
        avg_confidence = sum(confidence_scores.values()) / len(confidence_scores)
        if avg_confidence < self.human_review_threshold:
            return True

        return False
