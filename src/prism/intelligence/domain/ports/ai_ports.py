"""
Intelligence Domain Ports — AI Service Interfaces

Architectural Intent:
- Protocol-based ports define contracts for AI infrastructure adapters
- Domain layer depends only on these protocols, never on concrete implementations
- Each port corresponds to a distinct AI capability in the enrichment pipeline
- Type hints use domain value objects to maintain ubiquitous language
- All operations are async — AI inference is inherently I/O-bound
"""

from __future__ import annotations

from typing import Protocol

from prism.intelligence.domain.value_objects.ai_output import (
    ExtractedAttributes,
    GeneratedDescription,
)
from prism.intelligence.domain.value_objects.model_config import BrandVoiceConfig
from prism.shared.domain.value_objects import ImageRef, Locale


class AttributeExtractionPort(Protocol):
    """
    Port for AI-powered attribute extraction from product imagery.

    Implementations use computer vision models (e.g., Gemini Vision) to
    identify material, colour, pattern, and other luxury-relevant attributes
    from product photographs.
    """

    async def extract_attributes(
        self,
        images: list[ImageRef],
        context: dict[str, str],
    ) -> ExtractedAttributes:
        """
        Extract structured product attributes from one or more images.

        Args:
            images: Product image references in Cloud Storage.
            context: Additional context (e.g., product category, brand)
                     to improve extraction accuracy.

        Returns:
            Structured attributes with per-field confidence scores.
        """
        ...


class DescriptionGenerationPort(Protocol):
    """
    Port for AI-powered brand-voice description generation.

    Implementations use large language models to produce luxury-grade
    product descriptions that match the brand's tone and style.
    """

    async def generate_description(
        self,
        attributes: dict[str, str],
        voice_config: BrandVoiceConfig,
        locale: Locale,
    ) -> GeneratedDescription:
        """
        Generate a brand-voice product description from attributes.

        Args:
            attributes: Extracted or curated product attributes.
            voice_config: Brand-specific tone and style configuration.
            locale: Target locale for language and cultural adaptation.

        Returns:
            Generated description with metadata (tone, word count, locale).
        """
        ...


class EmbeddingGenerationPort(Protocol):
    """
    Port for generating vector embeddings from text and images.

    Implementations use embedding models to create dense vector
    representations for semantic search and similarity matching.
    """

    async def generate_text_embedding(self, text: str) -> list[float]:
        """
        Generate a text embedding vector.

        Args:
            text: Input text to embed (typically product description + attributes).

        Returns:
            Dense float vector suitable for vector index storage.
        """
        ...

    async def generate_multimodal_embedding(
        self,
        text: str,
        image: ImageRef,
    ) -> list[float]:
        """
        Generate a multimodal embedding from text and image together.

        Args:
            text: Textual description or attributes.
            image: Product image reference.

        Returns:
            Dense float vector combining text and visual semantics.
        """
        ...


class VectorIndexPort(Protocol):
    """
    Port for vector similarity search and index management.

    Implementations back onto vector databases (e.g., Vertex AI Vector Search,
    Pinecone) for nearest-neighbour retrieval.
    """

    async def upsert(
        self,
        product_id: str,
        vector: list[float],
    ) -> str:
        """
        Insert or update a product vector in the index.

        Args:
            product_id: Unique product identifier (used as vector key).
            vector: Dense float vector to store.

        Returns:
            The vector_id assigned by the index.
        """
        ...

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """
        Find the top-k most similar products to a query vector.

        Args:
            query_vector: Query embedding vector.
            top_k: Number of results to return.

        Returns:
            List of (product_id, similarity_score) tuples, descending by score.
        """
        ...
