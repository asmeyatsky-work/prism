"""
Intelligence Infrastructure Adapter — Gemini Description Generator

Architectural Intent:
- Implements DescriptionGenerationPort using Google Gemini
- Brand-voice-aware generation with tone, style guidelines, and few-shot examples
- Locale-aware for multilingual luxury markets
- Structured output via Pydantic schema ensures consistent response format
- Temperature and length are configurable via ModelConfig

Integration Notes:
- Requires GOOGLE_CLOUD_PROJECT environment variable
- BrandVoiceConfig drives prompt engineering for tone fidelity
- Few-shot examples from BrandVoiceConfig enable brand-specific style matching
"""

from __future__ import annotations

import json
import logging
from typing import Any

from prism.intelligence.domain.value_objects.ai_output import GeneratedDescription
from prism.intelligence.domain.value_objects.model_config import BrandVoiceConfig, ModelConfig
from prism.shared.domain.value_objects import Locale

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_CONFIG = ModelConfig(
    model_name="gemini-2.0-flash",
    version="latest",
    temperature=0.7,
    max_tokens=1024,
)


def _build_system_prompt(voice_config: BrandVoiceConfig, locale: Locale) -> str:
    """Construct the system prompt for brand-voice description generation."""
    tone_descriptions = {
        "luxury": "sophisticated, exclusive, and aspirational",
        "contemporary": "modern, approachable yet refined",
        "avant-garde": "bold, innovative, and boundary-pushing",
    }
    tone_desc = tone_descriptions.get(voice_config.tone.value, "sophisticated")

    prompt = f"""You are an expert luxury fashion copywriter for {voice_config.brand_name}.

Your writing tone is {tone_desc}.
Target language/locale: {locale.code}

Write a compelling product description that:
1. Opens with an evocative hook that captures the essence of the piece
2. Highlights key materials and craftsmanship details
3. Suggests styling occasions and pairings
4. Maintains the brand voice throughout
5. Is between 80-150 words"""

    if voice_config.style_guidelines:
        prompt += f"\n\nStyle guidelines:\n{voice_config.style_guidelines}"

    if voice_config.example_descriptions:
        prompt += "\n\nExample descriptions in this brand's voice:"
        for i, example in enumerate(voice_config.example_descriptions, 1):
            prompt += f"\n{i}. {example}"

    prompt += """

Return ONLY valid JSON with these fields:
- text: the generated description
- tone: the tone used
- locale: the locale code
- word_count: number of words in the description"""

    return prompt


class GeminiDescriptionGenerator:
    """
    Brand-voice description generator using Google Gemini.

    Produces luxury-grade product descriptions tailored to each brand's
    tone, style guidelines, and target locale. Uses few-shot examples
    from BrandVoiceConfig for consistent brand voice matching.
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

    async def generate_description(
        self,
        attributes: dict[str, str],
        voice_config: BrandVoiceConfig,
        locale: Locale,
    ) -> GeneratedDescription:
        """
        Generate a brand-voice product description from attributes.

        Args:
            attributes: Product attributes to describe.
            voice_config: Brand-specific tone and style configuration.
            locale: Target locale for language and cultural adaptation.

        Returns:
            GeneratedDescription with text, tone, locale, and word count.

        Raises:
            RuntimeError: If the Gemini API call or response parsing fails.
        """
        try:
            from google.cloud import aiplatform
            from vertexai.generative_models import GenerativeModel

            aiplatform.init(project=self._project_id, location=self._location)

            model = GenerativeModel(self._model_config.model_name)

            system_prompt = _build_system_prompt(voice_config, locale)

            # Format attributes as structured input
            attr_text = "\n".join(f"- {k}: {v}" for k, v in attributes.items() if v)
            user_prompt = f"Product attributes:\n{attr_text}\n\nGenerate the product description."

            generation_config = {
                "temperature": self._model_config.temperature,
                "max_output_tokens": self._model_config.max_tokens,
                "response_mime_type": "application/json",
            }

            response = await model.generate_content_async(
                [system_prompt, user_prompt],
                generation_config=generation_config,
            )

            parsed = json.loads(response.text)
            return self._parse_response(parsed, voice_config, locale)

        except ImportError:
            logger.warning(
                "Vertex AI SDK not installed. Returning empty description. "
                "Install with: pip install google-cloud-aiplatform"
            )
            return GeneratedDescription()

        except Exception as exc:
            logger.error("Description generation failed: %s", exc, exc_info=True)
            raise RuntimeError(f"Description generation failed: {exc}") from exc

    def _parse_response(
        self,
        parsed: dict[str, Any],
        voice_config: BrandVoiceConfig,
        locale: Locale,
    ) -> GeneratedDescription:
        """Parse Gemini JSON response into GeneratedDescription."""
        text = str(parsed.get("text", ""))
        word_count = len(text.split()) if text else 0

        return GeneratedDescription(
            text=text,
            tone=parsed.get("tone", voice_config.tone.value),
            locale=parsed.get("locale", locale.code),
            word_count=parsed.get("word_count", word_count),
        )
