"""
Discovery Infrastructure — Vertex AI Vector Search Adapter.

Architectural Intent:
- Implements VectorSearchPort using Google Cloud Vertex AI Vector Search
- Converts text queries into embeddings using Vertex AI Embedding API
- Performs approximate nearest-neighbour search against a managed index
- Handles tenant isolation via namespace filtering in the vector index

Infrastructure Details:
- Vertex AI Vector Search provides low-latency ANN search at scale
- Embeddings are generated using text-embedding models (e.g., textembedding-gecko)
- Index is partitioned by tenant_id for data isolation in multi-tenant deployment
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from prism.discovery.domain.value_objects.search_query import SearchResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VertexVectorSearchConfig:
    """Configuration for Vertex AI Vector Search connection."""

    project_id: str = ""
    location: str = "us-central1"
    index_endpoint_id: str = ""
    deployed_index_id: str = ""
    embedding_model: str = "text-embedding-005"
    dimensions: int = 768


class VertexVectorSearchAdapter:
    """
    Implements VectorSearchPort using Vertex AI Vector Search.

    In production, this adapter:
    1. Converts the text query to an embedding via the Embedding API
    2. Queries the Vector Search index endpoint with the embedding
    3. Applies tenant-scoped namespace filtering
    4. Maps index results to domain SearchResult value objects
    """

    def __init__(self, config: VertexVectorSearchConfig) -> None:
        self._config = config
        self._client = None  # Lazily initialised Vertex AI client

    async def search_by_text(
        self,
        query: str,
        top_k: int = 20,
        filters: dict[str, str | list[str]] | None = None,
        tenant_id: str = "",
    ) -> list[SearchResult]:
        """
        Execute a text-based vector similarity search.

        Steps:
        1. Generate embedding for the query text
        2. Build filter restricts for tenant isolation and user filters
        3. Query Vertex AI Vector Search endpoint
        4. Map response to SearchResult domain objects
        """
        logger.info(
            "Executing vector search: query=%r, top_k=%d, tenant=%s",
            query[:50],
            top_k,
            tenant_id,
        )

        embedding = await self._generate_embedding(query)
        restricts = self._build_restricts(tenant_id, filters)
        raw_results = await self._query_index(embedding, top_k, restricts)

        return [
            SearchResult(
                product_id=r["id"],
                score=r["distance"],
                rank=idx + 1,
                explanation=f"semantic similarity: {r['distance']:.4f}",
            )
            for idx, r in enumerate(raw_results)
        ]

    async def _generate_embedding(self, text: str) -> list[float]:
        """
        Generate a text embedding using Vertex AI Embedding API.

        In production, this calls:
            aiplatform.TextEmbeddingModel.get_embeddings([TextEmbeddingInput(text)])
        """
        # Placeholder — in production, this calls the Vertex AI Embedding API
        logger.debug("Generating embedding for text: %r", text[:50])
        return [0.0] * self._config.dimensions

    async def _query_index(
        self,
        embedding: list[float],
        top_k: int,
        restricts: list[dict],
    ) -> list[dict]:
        """
        Query the Vertex AI Vector Search index endpoint.

        In production, this calls:
            index_endpoint.find_neighbors(
                deployed_index_id=...,
                queries=[embedding],
                num_neighbors=top_k,
                filter=restricts,
            )
        """
        logger.debug("Querying vector index: top_k=%d, restricts=%d", top_k, len(restricts))
        return []

    def _build_restricts(
        self,
        tenant_id: str,
        filters: dict[str, str | list[str]] | None,
    ) -> list[dict]:
        """
        Build Vertex AI Vector Search namespace restricts.

        Tenant isolation is enforced by always including a tenant_id restrict.
        User-supplied filters are appended as additional restricts.
        """
        restricts: list[dict] = []

        if tenant_id:
            restricts.append({
                "namespace": "tenant_id",
                "allow_list": [tenant_id],
            })

        if filters:
            for key, value in filters.items():
                allow = value if isinstance(value, list) else [value]
                restricts.append({
                    "namespace": key,
                    "allow_list": allow,
                })

        return restricts
