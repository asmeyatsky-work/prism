"""Intelligence infrastructure adapters — concrete implementations of domain ports."""

from prism.intelligence.infrastructure.adapters.gemini_description_adapter import (
    GeminiDescriptionGenerator,
)
from prism.intelligence.infrastructure.adapters.vertex_ai_adapter import (
    VertexAIAttributeExtractor,
)
from prism.intelligence.infrastructure.adapters.vertex_embedding_adapter import (
    VertexEmbeddingAdapter,
)

__all__ = [
    "VertexAIAttributeExtractor",
    "GeminiDescriptionGenerator",
    "VertexEmbeddingAdapter",
]
