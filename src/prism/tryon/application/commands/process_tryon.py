"""
Try-On Application Command — Process Virtual Try-On

Architectural Intent:
- Orchestrates the full try-on pipeline: extract_pose -> compose_tryon -> result
- Customer image bytes flow through the pipeline in-memory only
- After pose extraction the bytes reference is dropped — no persistence
- Manages TryOnSession aggregate lifecycle (PENDING -> PROCESSING -> COMPOSITING -> COMPLETED)
- Returns CommandResult with TryOnResponseDTO on success

Pipeline:
  1. Validate consent and product category eligibility
  2. Create TryOnSession aggregate (PENDING)
  3. Extract body pose from customer image bytes (PROCESSING)
  4. Discard customer image bytes (privacy-by-design)
  5. Compose virtual try-on with product image + pose (COMPOSITING)
  6. Return result with signed URL (COMPLETED)
"""

from __future__ import annotations

import time

from prism.shared.application.dtos import CommandResult
from prism.shared.domain.value_objects import ImageRef

from prism.tryon.application.dtos.tryon_dto import (
    ConsentRequiredError,
    TryOnRequestDTO,
    TryOnResponseDTO,
)
from prism.tryon.domain.entities.tryon_session import (
    TryOnCategory,
    TryOnSession,
)
from prism.tryon.domain.ports.tryon_ports import BodyExtractionPort, CompositionPort
from prism.tryon.domain.services.tryon_validation_service import TryOnValidationService
from prism.tryon.domain.value_objects.composition import BrandTryOnConfig


class ProcessTryOnUseCase:
    """
    Application use case: process a virtual try-on request.

    Coordinates domain objects and infrastructure ports to execute the
    full try-on pipeline. Customer image bytes are held only for the
    duration of pose extraction and then discarded.
    """

    def __init__(
        self,
        body_extractor: BodyExtractionPort,
        compositor: CompositionPort,
        validation_service: TryOnValidationService | None = None,
    ) -> None:
        self._body_extractor = body_extractor
        self._compositor = compositor
        self._validation = validation_service or TryOnValidationService()

    async def execute(
        self,
        request: TryOnRequestDTO,
        product_image: ImageRef,
    ) -> CommandResult[TryOnResponseDTO]:
        """
        Execute the try-on pipeline.

        Args:
            request: Validated try-on request DTO (contains customer image bytes).
            product_image: Reference to the product image in Cloud Storage.

        Returns:
            CommandResult containing TryOnResponseDTO on success, or error on failure.
        """
        start_time_ms = _current_time_ms()

        # --- Step 0: Validate consent ---
        try:
            request.validate_consent()
        except ConsentRequiredError as exc:
            return CommandResult.fail(str(exc), code="CONSENT_REQUIRED")

        # --- Step 1: Validate product category ---
        if not self._validation.validate_product_category(request.category):
            return CommandResult.fail(
                f"Product category '{request.category}' is not supported for try-on",
                code="UNSUPPORTED_CATEGORY",
            )

        # --- Step 2: Create session aggregate ---
        session = TryOnSession(
            session_id="",  # will use inherited id
            tenant_id=request.tenant_id,
            product_id=request.product_id,
            category=TryOnCategory(request.category),
            brand_config=BrandTryOnConfig(
                background_preset=request.background_preset,
                lighting_preset=request.lighting_preset,
            ),
        )
        session = session.start_processing()

        # --- Step 3: Extract body pose (customer image bytes in-memory only) ---
        try:
            pose = await self._body_extractor.extract_pose(request.customer_image)
            # Customer image bytes are NOT stored — the request DTO goes out of
            # scope after this use case returns, and we do not retain a reference.
        except (ValueError, RuntimeError) as exc:
            elapsed = _current_time_ms() - start_time_ms
            session = session.fail(
                reason=f"Body extraction failed: {exc}",
                processing_time_ms=elapsed,
            )
            return CommandResult.fail(
                f"Body extraction failed: {exc}", code="EXTRACTION_FAILED"
            )

        session = session.complete_body_extraction(pose)

        # --- Step 4: Compose try-on result ---
        try:
            composition = await self._compositor.compose_tryon(
                pose=pose,
                product_image=product_image,
                config=session.brand_config,
            )
        except RuntimeError as exc:
            elapsed = _current_time_ms() - start_time_ms
            session = session.fail(
                reason=f"Composition failed: {exc}",
                processing_time_ms=elapsed,
            )
            return CommandResult.fail(
                f"Composition failed: {exc}", code="COMPOSITION_FAILED"
            )

        elapsed = _current_time_ms() - start_time_ms
        session = session.complete_composition(
            result=composition,
            processing_time_ms=elapsed,
        )

        # --- Step 5: Build response ---
        within_budget = self._validation.validate_latency_budget(elapsed)

        response = TryOnResponseDTO(
            session_id=session.id,
            product_id=session.product_id,
            result_image_url=composition.result_image_url,
            confidence=composition.confidence,
            processing_time_ms=elapsed,
            within_latency_budget=within_budget,
        )

        return CommandResult.ok(response)


def _current_time_ms() -> int:
    """Return current monotonic time in milliseconds."""
    return int(time.monotonic() * 1000)
