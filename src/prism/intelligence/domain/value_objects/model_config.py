"""
Intelligence Value Objects — Model and Brand Voice Configuration

Architectural Intent:
- ModelConfig encapsulates AI model parameters for reproducibility and versioning
- BrandVoiceConfig drives tone-aware description generation per brand tenant
- Both are frozen dataclasses — passed into ports, never mutated
- Example descriptions in BrandVoiceConfig enable few-shot prompting
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from prism.shared.domain.value_objects import ValueObject


class Tone(str, Enum):
    """Brand voice tone presets for luxury description generation."""

    LUXURY = "luxury"
    CONTEMPORARY = "contemporary"
    AVANT_GARDE = "avant-garde"


@dataclass(frozen=True)
class ModelConfig(ValueObject):
    """
    AI model configuration for reproducible inference.

    Passed to infrastructure adapters to control model selection,
    generation parameters, and versioning for audit trails.
    """

    model_name: str
    version: str
    temperature: float = 0.3
    max_tokens: int = 1024

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {self.temperature}")
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be positive, got {self.max_tokens}")


@dataclass(frozen=True)
class BrandVoiceConfig(ValueObject):
    """
    Brand-specific voice configuration for description generation.

    Encapsulates the tone, style guidelines, and example descriptions
    that shape how AI-generated copy reads for each luxury brand tenant.
    Example descriptions enable few-shot prompting in the generation adapter.
    """

    brand_name: str
    tone: Tone = Tone.LUXURY
    style_guidelines: str = ""
    example_descriptions: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        if not self.brand_name or not self.brand_name.strip():
            raise ValueError("brand_name cannot be empty")
