"""
Payment Application — Data Transfer Objects

Architectural Intent:
- Pydantic models for structured input/output at use case boundaries
- PaymentRequestDTO: inbound data from MCP tools or API calls
- PaymentResponseDTO: outbound data returned from payment use cases
- FXComparisonDTO: result of parallel FX rate shopping
- BNPLOptionsDTO: BNPL eligibility result for checkout presentation
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PaymentRequestDTO(BaseModel):
    """Inbound request to initiate a payment."""

    order_id: str
    tenant_id: str
    amount: float = Field(gt=0, description="Payment amount")
    currency: str = Field(description="ISO 4217 currency code for the payment")
    customer_currency: str = Field(description="Customer's preferred display currency")
    settlement_currency: str = Field(description="Merchant's settlement currency")
    card_token: str = Field(description="Tokenised card reference from vault")
    card_type: str = Field(default="", description="Card network (visa, mastercard, amex)")
    customer_id: str = Field(default="", description="Customer identifier for BNPL checks")


class PaymentResponseDTO(BaseModel):
    """Outbound result of a payment operation."""

    payment_id: str
    order_id: str
    status: str
    psp_id: str = ""
    psp_transaction_id: str = ""
    amount: float = 0.0
    currency: str = ""
    decline_reason: str | None = None
    retry_count: int = 0


class FXRateDTO(BaseModel):
    """Single FX rate quote from a provider."""

    source_currency: str
    target_currency: str
    rate: float
    provider: str
    quoted_at: datetime
    expires_at: datetime


class FXComparisonDTO(BaseModel):
    """Result of parallel FX rate comparison across providers."""

    rates: list[FXRateDTO]
    best_rate: FXRateDTO
    savings_amount: float = 0.0
    savings_currency: str = ""


class BNPLOptionDTO(BaseModel):
    """Single BNPL installment plan."""

    provider: str
    installments: int
    interest_rate: float
    min_amount: float
    max_amount: float
    currency: str


class BNPLOptionsDTO(BaseModel):
    """BNPL eligibility result for a customer and amount."""

    eligible: bool
    options: list[BNPLOptionDTO] = Field(default_factory=list)
