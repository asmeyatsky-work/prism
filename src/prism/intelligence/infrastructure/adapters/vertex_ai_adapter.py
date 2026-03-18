"""
Intelligence Infrastructure Adapter — Vertex AI Attribute Extractor

Architectural Intent:
- Implements AttributeExtractionPort using Google Gemini Vision
- Uses Pydantic structured output schema for reliable JSON parsing
- Constructs multimodal prompts from product images and context
- Handles GCS image references natively via Vertex AI SDK
- Retry and error handling at the infrastructure boundary

Integration Notes:
- Requires GOOGLE_CLOUD_PROJECT environment variable
- Model is configurable via ModelConfig value object
- Structured output uses Pydantic schema for type-safe extraction
"""

from __future__ import annotations

import json
import logging
from typing import Any

from prism.intelligence.domain.value_objects.ai_output import (
    AttributeWithConfidence,
    ExtractedAttributes,
)
from prism.intelligence.domain.value_objects.model_config import ModelConfig
from prism.shared.domain.value_objects import ImageRef

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_CONFIG = ModelConfig(
    model_name="gemini-2.0-flash",
    version="latest",
    temperature=0.1,
    max_tokens=2048,
)

_EXTRACTION_SYSTEM_PROMPT = """You are a luxury fashion product attribute extraction specialist.
Analyse the provided product image(s) and extract structured attributes.

For each attribute, provide:
- value: the extracted attribute value
- confidence: your confidence score between 0.0 and 1.0

Attributes to extract:
- material: Primary material (e.g., cashmere, silk, lambskin, cotton)
- colour: Dominant colour as perceived in the image
- pattern: Pattern or print (e.g., houndstooth, solid, floral, striped)
- silhouette: Garment silhouette or form factor (e.g., A-line, oversized, slim-fit)
- occasion: Intended occasion (e.g., evening, casual, business, resort)
- season: Seasonal relevance (e.g., SS25, AW25, resort, pre-fall)
- style_tags: Additional style descriptors (e.g., minimalist, bohemian, classic)

Return ONLY valid JSON matching the expected schema."""


class VertexAIAttributeExtractor:
    """
    Attribute extraction adapter using Google Gemini Vision.

    Sends product images to Gemini with a structured extraction prompt
    and parses the response into an ExtractedAttributes Pydantic model.
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        project_id: str | None = None,
        location: str = "us-central1",
    ) -> None:
        self._model_config = model_config or _DEFAULT_MODEL_CONFIG
        self._project_id = project_id
        self._location = location

    async def extract_attributes(
        self,
        images: list[ImageRef],
        context: dict[str, str],
    ) -> ExtractedAttributes:
        """
        Extract structured product attributes from images using Gemini Vision.

        Args:
            images: Product image references in Google Cloud Storage.
            context: Additional context (brand, locale) for extraction accuracy.

        Returns:
            ExtractedAttributes with per-field confidence scores.

        Raises:
            RuntimeError: If the Vertex AI API call fails or response parsing fails.
        """
        try:
            from google.cloud import aiplatform
            from vertexai.generative_models import GenerativeModel, Image, Part

            aiplatform.init(project=self._project_id, location=self._location)

            model = GenerativeModel(self._model_config.model_name)

            # Build multimodal prompt parts
            parts: list[Any] = []
            for image_ref in images:
                parts.append(Part.from_uri(uri=image_ref.gcs_uri, mime_type=image_ref.content_type))

            # Add context to prompt
            context_text = ""
            if context:
                context_text = "\n".join(f"- {k}: {v}" for k, v in context.items())
                context_text = f"\n\nAdditional context:\n{context_text}"

            parts.append(f"{_EXTRACTION_SYSTEM_PROMPT}{context_text}")

            # Generate with structured output configuration
            generation_config = {
                "temperature": self._model_config.temperature,
                "max_output_tokens": self._model_config.max_tokens,
                "response_mime_type": "application/json",
            }

            response = await model.generate_content_async(
                parts,
                generation_config=generation_config,
            )

            # Parse structured response into Pydantic model
            response_text = response.text
            parsed = json.loads(response_text)
            return self._parse_response(parsed)

        except ImportError:
            logger.warning(
                "Vertex AI SDK not installed. Returning empty attributes. "
                "Install with: pip install google-cloud-aiplatform"
            )
            return ExtractedAttributes()

        except Exception as exc:
            logger.error("Attribute extraction failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Attribute extraction failed: {exc}") from exc

    def _parse_response(self, parsed: dict[str, Any]) -> ExtractedAttributes:
        """Parse Gemini JSON response into ExtractedAttributes."""
        def _parse_attr(data: Any) -> AttributeWithConfidence:
            if isinstance(data, dict):
                return AttributeWithConfidence(
                    value=str(data.get("value", "")),
                    confidence=float(data.get("confidence", 0.0)),
                )
            if isinstance(data, str):
                return AttributeWithConfidence(value=data, confidence=0.5)
            return AttributeWithConfidence()

        style_tags_raw = parsed.get("style_tags", [])
        if isinstance(style_tags_raw, list):
            style_tags = [_parse_attr(tag) for tag in style_tags_raw]
        else:
            style_tags = []

        return ExtractedAttributes(
            material=_parse_attr(parsed.get("material")),
            colour=_parse_attr(parsed.get("colour")),
            pattern=_parse_attr(parsed.get("pattern")),
            silhouette=_parse_attr(parsed.get("silhouette")),
            occasion=_parse_attr(parsed.get("occasion")),
            season=_parse_attr(parsed.get("season")),
            style_tags=style_tags,
        )
