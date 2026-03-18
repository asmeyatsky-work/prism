"""
Intelligence Value Objects — AI Output Schemas

Architectural Intent:
- Pydantic BaseModel for structured AI output parsing (Gemini structured output)
- ExtractedAttributes maps directly to the Gemini Vision response schema
- Each attribute carries its own confidence score for granular quality control
- EmbeddingVector is a frozen dataclass (pure value object, no AI parsing needed)
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from prism.shared.domain.value_objects import ValueObject


class AttributeWithConfidence(BaseModel):
    """A single extracted attribute value paired with its confidence score."""

    value: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ExtractedAttributes(BaseModel):
    """
    Structured output from AI attribute extraction.

    Each field corresponds to a luxury product attribute extracted from
    product images via Gemini Vision. Confidence scores enable downstream
    quality gating and human review triggering.
    """

    material: AttributeWithConfidence = Field(
        default_factory=AttributeWithConfidence,
        description="Primary material (e.g., cashmere, silk, lambskin)",
    )
    colour: AttributeWithConfidence = Field(
        default_factory=AttributeWithConfidence,
        description="Dominant colour as perceived in imagery",
    )
    pattern: AttributeWithConfidence = Field(
        default_factory=AttributeWithConfidence,
        description="Pattern or print (e.g., houndstooth, solid, floral)",
    )
    silhouette: AttributeWithConfidence = Field(
        default_factory=AttributeWithConfidence,
        description="Garment silhouette or form factor (e.g., A-line, oversized)",
    )
    occasion: AttributeWithConfidence = Field(
        default_factory=AttributeWithConfidence,
        description="Intended occasion (e.g., evening, casual, business)",
    )
    season: AttributeWithConfidence = Field(
        default_factory=AttributeWithConfidence,
        description="Seasonal relevance (e.g., SS25, AW25, resort)",
    )
    style_tags: list[AttributeWithConfidence] = Field(
        default_factory=list,
        description="Additional style descriptors with confidence",
    )

    def to_flat_dict(self) -> dict[str, str]:
        """Return attribute values as a flat dict, excluding style_tags."""
        return {
            "material": self.material.value,
            "colour": self.colour.value,
            "pattern": self.pattern.value,
            "silhouette": self.silhouette.value,
            "occasion": self.occasion.value,
            "season": self.season.value,
        }

    def confidence_scores(self) -> dict[str, float]:
        """Return confidence scores as a flat dict for quality gating."""
        scores = {
            "material": self.material.confidence,
            "colour": self.colour.confidence,
            "pattern": self.pattern.confidence,
            "silhouette": self.silhouette.confidence,
            "occasion": self.occasion.confidence,
            "season": self.season.confidence,
        }
        if self.style_tags:
            scores["style_tags"] = min(tag.confidence for tag in self.style_tags)
        return scores


class GeneratedDescription(BaseModel):
    """
    Structured output from AI description generation.

    Captures the generated text along with metadata about tone, locale,
    and length for quality assurance and audit trails.
    """

    text: str = Field(default="", description="The generated product description")
    tone: str = Field(
        default="luxury",
        description="Tone used for generation (luxury, contemporary, avant-garde)",
    )
    locale: str = Field(default="en", description="Locale code for the generated text")
    word_count: int = Field(default=0, ge=0, description="Word count of generated text")


@dataclass(frozen=True)
class EmbeddingVector(ValueObject):
    """
    Reference to a stored embedding vector.

    The actual vector data lives in the vector index infrastructure;
    this value object holds the reference and metadata needed to
    retrieve or identify it.
    """

    vector_id: str
    dimensions: int
    model_name: str
