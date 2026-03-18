"""
Try-On Application DTOs — Pydantic models for structured input/output

Architectural Intent:
- Pydantic models for request validation and structured AI output
- TryOnRequestDTO enforces consent requirement at the API boundary
- TryOnResponseDTO provides a serialisable view of the try-on result
- Customer image bytes are accepted as input but NEVER persisted in DTOs

Privacy:
- TryOnRequestDTO.customer_image is bytes (in-memory only)
- The field is excluded from serialisation and logging via repr=False
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TryOnRequestDTO(BaseModel):
    """
    Inbound request to initiate a virtual try-on session.

    The customer_image field carries raw bytes in-memory. It is excluded
    from JSON serialisation (``exclude=True``) and repr to prevent
    accidental logging of customer data.

    Attributes:
        customer_image: Raw image bytes from the customer (JPEG/PNG).
        product_id: The product to virtually try on.
        tenant_id: Brand/tenant scope.
        consent: Explicit customer consent for image processing (required=True).
        category: Product category for try-on eligibility validation.
        background_preset: Optional brand background override.
        lighting_preset: Optional brand lighting override.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    customer_image: bytes = Field(
        ...,
        exclude=True,
        repr=False,
        description="Customer image bytes — processed in-memory only, never persisted",
    )
    product_id: str = Field(
        ...,
        min_length=1,
        description="Product ID to try on",
    )
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Tenant/brand identifier",
    )
    consent: bool = Field(
        ...,
        description="Explicit customer consent for image processing",
    )
    category: str = Field(
        default="APPAREL",
        description="Product category (APPAREL, ACCESSORIES, EYEWEAR, JEWELLERY)",
    )
    background_preset: str = Field(
        default="studio_white",
        description="Brand-specific background preset",
    )
    lighting_preset: str = Field(
        default="soft_diffused",
        description="Brand-specific lighting preset",
    )

    def validate_consent(self) -> None:
        """Raise if consent is not granted."""
        if not self.consent:
            raise ConsentRequiredError(
                "Customer consent is required for virtual try-on image processing"
            )


class TryOnResponseDTO(BaseModel):
    """
    Outbound response for a completed virtual try-on session.

    Attributes:
        session_id: Unique session identifier.
        product_id: The product that was tried on.
        result_image_url: Signed URL to the composited try-on image.
        confidence: Model confidence score (0.0-1.0).
        processing_time_ms: Total processing time in milliseconds.
        within_latency_budget: Whether the result met the P95 SLA.
    """

    session_id: str
    product_id: str
    result_image_url: str
    confidence: float = Field(ge=0.0, le=1.0)
    processing_time_ms: int = Field(ge=0)
    within_latency_budget: bool = True


class OutfitDTO(BaseModel):
    """
    Outbound response for an outfit composition ("Complete the Look").

    Attributes:
        session_id: The try-on session that triggered the outfit suggestion.
        product_ids: Tuple of product IDs composing the outfit.
        style_score: AI-computed coherence score (0.0-1.0).
        occasion: Target occasion label.
    """

    session_id: str
    product_ids: list[str]
    style_score: float = Field(ge=0.0, le=1.0)
    occasion: str = ""


class ConsentRequiredError(Exception):
    """Raised when customer consent is not provided for image processing."""
