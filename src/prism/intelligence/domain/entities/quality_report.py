"""
Intelligence Domain Entity — QualityReport

Architectural Intent:
- Captures a point-in-time quality assessment of product data completeness
- Scores span image quality, attribute completeness, and description richness
- Recommendations guide human operators toward data improvements
- Frozen dataclass — reports are immutable snapshots, never edited
- Tenant-scoped via TenantId value object
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prism.shared.domain.entities import Entity
from prism.shared.domain.value_objects import TenantId


@dataclass(frozen=True)
class QualityReport(Entity):
    """
    Immutable quality assessment report for a product's data completeness.

    Scores range from 0.0 to 1.0:
    - completeness_score: How many required attributes are present and valid
    - image_quality_score: Technical quality of product imagery
    - description_richness_score: Depth and luxury-appropriateness of copy
    - overall_score: Weighted composite of all sub-scores

    Recommendations are actionable strings for human operators.
    """

    product_id: str = ""
    tenant_id: TenantId = field(default_factory=lambda: TenantId(value="default"))
    completeness_score: float = 0.0
    image_quality_score: float = 0.0
    description_richness_score: float = 0.0
    overall_score: float = 0.0
    recommendations: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        """Validate all scores are within the 0.0-1.0 range."""
        for field_name in (
            "completeness_score",
            "image_quality_score",
            "description_richness_score",
            "overall_score",
        ):
            value = getattr(self, field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{field_name} must be between 0.0 and 1.0, got {value}"
                )

    @property
    def is_acceptable(self) -> bool:
        """Whether the overall quality meets the minimum threshold for publishing."""
        return self.overall_score >= 0.7

    @property
    def needs_attention(self) -> bool:
        """Whether any individual score falls below the attention threshold."""
        return any(
            score < 0.5
            for score in (
                self.completeness_score,
                self.image_quality_score,
                self.description_richness_score,
            )
        )
