"""
Intelligence Infrastructure Adapter — Vertex AI Embedding and Vector Index

Architectural Intent:
- Implements both EmbeddingGenerationPort and VectorIndexPort
- Uses Vertex AI text-embedding and multimodal-embedding models
- Vector index operations use Vertex AI Vector Search (Matching Engine)
- Separation of embedding generation from index storage allows flexible deployment
- All operations are async for non-blocking I/O

Integration Notes:
- Requires GOOGLE_CLOUD_PROJECT environment variable
- Vector index must be pre-created in Vertex AI Vector Search
- Embedding dimensions are model-dependent (text-embedding-005: 768)
"""

from __future__ import annotations

import logging
from uuid import uuid4

from prism.intelligence.domain.value_objects.model_config import ModelConfig
from prism.shared.domain.value_objects import ImageRef

logger = logging.getLogger(__name__)

_DEFAULT_TEXT_EMBEDDING_CONFIG = ModelConfig(
    model_name="text-embedding-005",
    version="latest",
    temperature=0.0,
    max_tokens=256,
)

_DEFAULT_MULTIMODAL_CONFIG = ModelConfig(
    model_name="multimodalembedding@001",
    version="latest",
    temperature=0.0,
    max_tokens=256,
)


class VertexEmbeddingAdapter:
    """
    Embedding generation and vector index adapter using Vertex AI.

    Generates text and multimodal embeddings via Vertex AI embedding models,
    and manages vector storage via Vertex AI Vector Search (Matching Engine).
    """

    def __init__(
        self,
        text_model_config: ModelConfig | None = None,
        multimodal_model_config: ModelConfig | None = None,
        project_id: str | None = None,
        location: str = "us-central1",
        index_endpoint_id: str | None = None,
        deployed_index_id: str | None = None,
    ) -> None:
        self._text_config = text_model_config or _DEFAULT_TEXT_EMBEDDING_CONFIG
        self._multimodal_config = multimodal_model_config or _DEFAULT_MULTIMODAL_CONFIG
        self._project_id = project_id
        self._location = location
        self._index_endpoint_id = index_endpoint_id
        self._deployed_index_id = deployed_index_id

    async def generate_text_embedding(self, text: str) -> list[float]:
        """
        Generate a text embedding vector using Vertex AI.

        Args:
            text: Input text to embed.

        Returns:
            Dense float vector (768 dimensions for text-embedding-005).

        Raises:
            RuntimeError: If the embedding API call fails.
        """
        try:
            from vertexai.language_models import TextEmbeddingInput, TextEmbeddingModel

            model = TextEmbeddingModel.from_pretrained(self._text_config.model_name)

            embedding_input = TextEmbeddingInput(
                text=text,
                task_type="RETRIEVAL_DOCUMENT",
            )

            embeddings = model.get_embeddings([embedding_input])
            return embeddings[0].values

        except ImportError:
            logger.warning(
                "Vertex AI SDK not installed. Returning zero vector. "
                "Install with: pip install google-cloud-aiplatform"
            )
            return [0.0] * 768

        except Exception as exc:
            logger.error("Text embedding generation failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Text embedding generation failed: {exc}") from exc

    async def generate_multimodal_embedding(
        self,
        text: str,
        image: ImageRef,
    ) -> list[float]:
        """
        Generate a multimodal embedding combining text and image.

        Args:
            text: Textual description or attributes.
            image: Product image reference in Cloud Storage.

        Returns:
            Dense float vector combining text and visual semantics.

        Raises:
            RuntimeError: If the multimodal embedding API call fails.
        """
        try:
            from vertexai.vision_models import (
                Image as VisionImage,
                MultiModalEmbeddingModel,
            )

            model = MultiModalEmbeddingModel.from_pretrained(
                self._multimodal_config.model_name
            )

            vision_image = VisionImage.load_from_file(image.gcs_uri)

            embeddings = model.get_embeddings(
                image=vision_image,
                contextual_text=text,
            )

            return embeddings.image_embedding

        except ImportError:
            logger.warning(
                "Vertex AI SDK not installed. Returning zero vector. "
                "Install with: pip install google-cloud-aiplatform"
            )
            return [0.0] * 1408

        except Exception as exc:
            logger.error(
                "Multimodal embedding generation failed: %s", exc, exc_info=True
            )
            raise RuntimeError(
                f"Multimodal embedding generation failed: {exc}"
            ) from exc

    async def upsert(
        self,
        product_id: str,
        vector: list[float],
    ) -> str:
        """
        Insert or update a product vector in Vertex AI Vector Search.

        Args:
            product_id: Unique product identifier used as the vector key.
            vector: Dense float vector to store.

        Returns:
            The vector_id (same as product_id for idempotent upserts).

        Raises:
            RuntimeError: If the vector index upsert fails.
        """
        try:
            from google.cloud import aiplatform

            aiplatform.init(project=self._project_id, location=self._location)

            index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
                index_endpoint_name=self._index_endpoint_id,
            )

            index_endpoint.upsert_datapoints(
                deployed_index_id=self._deployed_index_id,
                datapoints=[
                    {
                        "datapoint_id": product_id,
                        "feature_vector": vector,
                    }
                ],
            )

            logger.info(
                "Upserted vector for product %s (dims=%d)",
                product_id,
                len(vector),
            )
            return product_id

        except ImportError:
            logger.warning(
                "Vertex AI SDK not installed. Returning generated vector_id. "
                "Install with: pip install google-cloud-aiplatform"
            )
            return f"vec_{product_id}_{uuid4().hex[:8]}"

        except Exception as exc:
            logger.error("Vector upsert failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Vector upsert failed: {exc}") from exc

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

        Raises:
            RuntimeError: If the vector search fails.
        """
        try:
            from google.cloud import aiplatform

            aiplatform.init(project=self._project_id, location=self._location)

            index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
                index_endpoint_name=self._index_endpoint_id,
            )

            response = index_endpoint.find_neighbors(
                deployed_index_id=self._deployed_index_id,
                queries=[query_vector],
                num_neighbors=top_k,
            )

            results: list[tuple[str, float]] = []
            if response and response[0]:
                for neighbor in response[0]:
                    results.append((neighbor.id, neighbor.distance))

            return results

        except ImportError:
            logger.warning(
                "Vertex AI SDK not installed. Returning empty results. "
                "Install with: pip install google-cloud-aiplatform"
            )
            return []

        except Exception as exc:
            logger.error("Vector search failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Vector search failed: {exc}") from exc
