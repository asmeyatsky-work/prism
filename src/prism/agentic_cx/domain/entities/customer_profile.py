"""
Agentic CX — Customer Profile Entity (ContextOps)

Architectural Intent:
- CustomerProfile aggregates customer context for agent personalisation
- Part of the ContextOps pattern: rich context enables better AI responses
- Preferences, style tags, and size profile drive product recommendations
- Purchase history and wishlist IDs reference entities in Commerce BC
- Profile is loaded at conversation start and updated after each interaction
- Immutable entity — updates return new instances
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from prism.shared.domain.entities import Entity
from prism.shared.domain.value_objects import Locale


@dataclass(frozen=True)
class CustomerProfile(Entity):
    """
    Customer context for agent personalisation.

    Aggregates preferences, style information, purchase history,
    and sizing data to enable the agent to make contextually
    relevant recommendations without re-asking the customer.

    This is the ContextOps entity — the richer the profile,
    the better the agent's first-turn accuracy.
    """

    customer_id: str = ""
    tenant_id: str = ""
    preferences: dict[str, Any] = field(default_factory=dict)
    style_tags: tuple[str, ...] = ()
    purchase_history_ids: tuple[str, ...] = ()
    wishlist_ids: tuple[str, ...] = ()
    size_profile: dict[str, Any] = field(default_factory=dict)
    preferred_locale: Locale = field(default_factory=lambda: Locale(language="en"))
    conversation_count: int = 0

    def add_style_tag(self, tag: str) -> CustomerProfile:
        """Add a style tag if not already present."""
        if tag in self.style_tags:
            return self
        return replace(
            self,
            style_tags=self.style_tags + (tag,),
            **self._touch(),
        )

    def remove_style_tag(self, tag: str) -> CustomerProfile:
        """Remove a style tag if present."""
        if tag not in self.style_tags:
            return self
        return replace(
            self,
            style_tags=tuple(t for t in self.style_tags if t != tag),
            **self._touch(),
        )

    def update_preferences(self, new_preferences: dict[str, Any]) -> CustomerProfile:
        """Merge new preferences into existing ones."""
        merged = {**self.preferences, **new_preferences}
        return replace(self, preferences=merged, **self._touch())

    def update_size_profile(self, size_data: dict[str, Any]) -> CustomerProfile:
        """Update sizing information (e.g. from virtual try-on results)."""
        merged = {**self.size_profile, **size_data}
        return replace(self, size_profile=merged, **self._touch())

    def add_purchase(self, order_id: str) -> CustomerProfile:
        """Record a purchase by appending the order ID."""
        if order_id in self.purchase_history_ids:
            return self
        return replace(
            self,
            purchase_history_ids=self.purchase_history_ids + (order_id,),
            **self._touch(),
        )

    def add_to_wishlist(self, product_id: str) -> CustomerProfile:
        """Add a product to the customer's wishlist."""
        if product_id in self.wishlist_ids:
            return self
        return replace(
            self,
            wishlist_ids=self.wishlist_ids + (product_id,),
            **self._touch(),
        )

    def remove_from_wishlist(self, product_id: str) -> CustomerProfile:
        """Remove a product from the customer's wishlist."""
        return replace(
            self,
            wishlist_ids=tuple(pid for pid in self.wishlist_ids if pid != product_id),
            **self._touch(),
        )

    def increment_conversation_count(self) -> CustomerProfile:
        """Increment the total conversation count for this customer."""
        return replace(
            self,
            conversation_count=self.conversation_count + 1,
            **self._touch(),
        )

    def has_purchase_history(self) -> bool:
        """Check if the customer has any recorded purchases."""
        return len(self.purchase_history_ids) > 0

    def is_new_customer(self) -> bool:
        """Check if this is the customer's first conversation."""
        return self.conversation_count == 0

    def to_agent_context(self) -> dict[str, Any]:
        """
        Export profile as a context dictionary for LLM prompt injection.

        This is the ContextOps payload — structured customer data that
        the agent uses to personalise recommendations and responses.
        """
        return {
            "customer_id": self.customer_id,
            "is_returning": not self.is_new_customer(),
            "conversation_count": self.conversation_count,
            "preferences": self.preferences,
            "style_tags": list(self.style_tags),
            "has_purchase_history": self.has_purchase_history(),
            "recent_purchases": list(self.purchase_history_ids[-5:]),
            "wishlist_count": len(self.wishlist_ids),
            "size_profile": self.size_profile,
            "locale": self.preferred_locale.code,
        }
