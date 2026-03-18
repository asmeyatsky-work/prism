"""Intelligence domain ports — protocol-based interfaces for AI and quality services."""

from prism.intelligence.domain.ports.ai_ports import (
    AttributeExtractionPort,
    DescriptionGenerationPort,
    EmbeddingGenerationPort,
    VectorIndexPort,
)
from prism.intelligence.domain.ports.quality_ports import (
    ImageQualityPort,
    QualityReportRepositoryPort,
)

__all__ = [
    "AttributeExtractionPort",
    "DescriptionGenerationPort",
    "EmbeddingGenerationPort",
    "VectorIndexPort",
    "ImageQualityPort",
    "QualityReportRepositoryPort",
]
