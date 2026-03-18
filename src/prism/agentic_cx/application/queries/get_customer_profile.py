"""
Agentic CX — Get Customer Profile Query

Architectural Intent:
- Read-only query to retrieve customer profile for ContextOps
- Returns CustomerProfileDTO without mutating any state
- Profile data drives agent personalisation and recommendation quality
"""

from __future__ import annotations

from prism.shared.application.dtos import QueryResult

from prism.agentic_cx.application.dtos.agent_dto import CustomerProfileDTO
from prism.agentic_cx.domain.entities.customer_profile import CustomerProfile
from prism.agentic_cx.domain.ports.agent_ports import CustomerProfilePort


class GetCustomerProfileQuery:
    """Query: retrieve a customer profile by customer ID and tenant."""

    def __init__(self, customer_profile_port: CustomerProfilePort) -> None:
        self._customer_profile_port = customer_profile_port

    async def execute(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> QueryResult[CustomerProfileDTO]:
        """
        Retrieve a customer profile.

        Returns QueryResult.empty() if no profile exists.
        """
        profile = await self._customer_profile_port.get_profile(
            customer_id=customer_id,
            tenant_id=tenant_id,
        )
        if profile is None:
            return QueryResult.empty()
        return QueryResult.ok(_to_dto(profile))


def _to_dto(profile: CustomerProfile) -> CustomerProfileDTO:
    """Convert a CustomerProfile entity to its DTO representation."""
    return CustomerProfileDTO(
        customer_id=profile.customer_id,
        tenant_id=profile.tenant_id,
        preferences=profile.preferences,
        style_tags=list(profile.style_tags),
        purchase_history_ids=list(profile.purchase_history_ids),
        wishlist_ids=list(profile.wishlist_ids),
        size_profile=profile.size_profile,
        preferred_locale=profile.preferred_locale.code,
        conversation_count=profile.conversation_count,
        is_new_customer=profile.is_new_customer(),
    )
