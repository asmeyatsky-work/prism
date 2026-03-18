"""
Brand Entity

Architectural Intent:
- Represents a luxury retail brand within the multi-tenant platform
- Tenant-scoped — each Brand belongs to exactly one TenantId
- tone_profile configures AI voice for generated product descriptions,
  ensuring brand consistency across enrichment pipelines
- Frozen dataclass for immutability per skill2026 Rule 3
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prism.shared.domain.entities import Entity
from prism.shared.domain.value_objects import ImageRef, Locale, TenantId


@dataclass(frozen=True)
class Brand(Entity):
    """
    Brand entity — represents a luxury retail brand in the platform.

    Each tenant in PRISM corresponds to a brand. The Brand entity stores
    brand-level configuration used across the Catalogue context, particularly
    for AI enrichment (tone_profile) and multi-locale support.

    Attributes:
        name: Brand display name (e.g. "Maison Lumiere").
        tenant_id: The tenant this brand belongs to.
        description: Brand description / mission statement.
        logo: Reference to the brand logo asset in Cloud Storage.
        locales: Supported locales for this brand's catalogue.
        tone_profile: AI voice configuration for generated descriptions.
            Describes the brand's editorial tone (e.g. "sophisticated,
            understated luxury, French heritage emphasis").
    """

    name: str = ""
    tenant_id: TenantId = field(default_factory=lambda: TenantId(value="default"))
    description: str = ""
    logo: ImageRef | None = None
    locales: tuple[Locale, ...] = ()
    tone_profile: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Brand name cannot be empty")

    def update_tone_profile(self, tone_profile: str) -> Brand:
        """
        Update the brand's AI tone profile for description generation.

        Args:
            tone_profile: New tone profile string describing the brand voice.

        Returns:
            New Brand instance with the updated tone profile.
        """
        from dataclasses import replace

        return replace(self, tone_profile=tone_profile, **self._touch())

    def add_locale(self, locale: Locale) -> Brand:
        """
        Add a supported locale to the brand's catalogue.

        Args:
            locale: Locale to add.

        Returns:
            New Brand instance with the locale appended.
        """
        from dataclasses import replace

        if locale in self.locales:
            return self
        return replace(self, locales=self.locales + (locale,), **self._touch())
