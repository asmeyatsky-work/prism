"""
Catalogue Enrichment Ports

Architectural Intent:
- Protocol-based interfaces for AI enrichment and embedding services
- Infrastructure adapters (Vertex AI, OpenAI, etc.) implement these protocols
- Decouples the domain from specific AI provider implementations
- Supports the enrichment lifecycle: extract attributes -> generate descriptions -> embed

Design Notes:
- CatalogueEnrichmentPort handles structured attribute extraction and text generation
- EmbeddingPort handles vector embedding for semantic search in Discovery context
- Both are async for integration with Cloud AI APIs
"""

from __future__ import annotations

from typing import Protocol

from prism.catalogue.domain.entities.product import Product


class CatalogueEnrichmentPort(Protocol):
    """
    Port for AI-powered product enrichment.

    Implementations use LLMs (Gemini, Claude) to extract structured attributes
    from product data and generate editorial descriptions in the brand's voice.
    """

    async def extract_attributes(self, product: Product) -> dict[str, str]:
        """
        Extract structured product attributes using AI.

        Analyses product images, name, and existing description to produce
        structured attributes (material, colour, pattern, etc.) conforming
        to the PRISM Unified Product Schema.

        Args:
            product: The Product aggregate to enrich.

        Returns:
            Dictionary of extracted attribute name-value pairs.
        """
        ...

    async def generate_description(self, product: Product, tone: str) -> str:
        """
        Generate an editorial product description in the brand's voice.

        Uses the product's attributes, images, and the brand's tone profile
        to produce a luxury-grade editorial description.

        Args:
            product: The Product aggregate to describe.
            tone: Brand tone profile string (e.g. "sophisticated, understated luxury").

        Returns:
            Generated editorial description string.
        """
        ...


class EmbeddingPort(Protocol):
    """
    Port for product embedding generation and indexing.

    Implementations produce vector embeddings for semantic search and
    similarity-based product discovery.
    """

    async def generate_embedding(self, product: Product) -> list[float]:
        """
        Generate a vector embedding for the given product.

        Combines product name, description, attributes, and category into
        a text representation, then produces a dense vector embedding.

        Args:
            product: The Product aggregate to embed.

        Returns:
            List of floats representing the product embedding vector.
        """
        ...

    async def index_embedding(
        self, product_id: str, vector: list[float]
    ) -> str:
        """
        Index a product embedding in the vector store.

        Stores the embedding vector for nearest-neighbour retrieval by
        the Discovery context's semantic search.

        Args:
            product_id: The product's domain ID.
            vector: The embedding vector to index.

        Returns:
            The vector store ID for the indexed embedding.
        """
        ...
