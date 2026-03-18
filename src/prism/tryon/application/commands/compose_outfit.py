"""
Try-On Application Command — Compose Outfit (Phase 2)

Architectural Intent:
- Orchestrates the "Complete the Look" feature
- Takes a seed product from a try-on session and suggests complementary items
- Uses the StyleMatchingPort to generate outfit recommendations
- Emits OutfitComposedEvent for engagement tracking

Phase 2: This use case is scaffolded for future implementation.
The core try-on pipeline (ProcessTryOnUseCase) is Phase 1.
"""

from __future__ import annotations

from prism.shared.application.dtos import CommandResult

from prism.tryon.application.dtos.tryon_dto import OutfitDTO
from prism.tryon.domain.events.tryon_events import OutfitComposedEvent
from prism.tryon.domain.ports.tryon_ports import StyleMatchingPort


class ComposeOutfitUseCase:
    """
    Application use case: compose an outfit suggestion for a try-on session.

    Takes the product being tried on and generates a "Complete the Look"
    outfit recommendation using the StyleMatchingPort.
    """

    def __init__(self, style_matcher: StyleMatchingPort) -> None:
        self._style_matcher = style_matcher

    async def execute(
        self,
        session_id: str,
        product_id: str,
        tenant_id: str,
        catalogue_context: dict[str, object] | None = None,
    ) -> CommandResult[OutfitDTO]:
        """
        Generate an outfit composition for the given product.

        Args:
            session_id: The try-on session that initiated the request.
            product_id: The seed product for outfit generation.
            tenant_id: Brand/tenant scope.
            catalogue_context: Additional catalogue metadata for the style model.

        Returns:
            CommandResult containing OutfitDTO on success, or error on failure.
        """
        context = catalogue_context or {}

        try:
            outfit = await self._style_matcher.suggest_outfit(
                product_id=product_id,
                catalogue_context=context,
            )
        except RuntimeError as exc:
            return CommandResult.fail(
                f"Outfit composition failed: {exc}",
                code="STYLE_MATCHING_FAILED",
            )

        # Build the outbound DTO
        dto = OutfitDTO(
            session_id=session_id,
            product_ids=list(outfit.items),
            style_score=outfit.style_score,
            occasion=outfit.occasion,
        )

        return CommandResult.ok(dto)
