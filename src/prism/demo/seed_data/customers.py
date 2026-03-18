"""
Mock Customer Profiles for PRISM Demo

Provides realistic customer personas for the AI Stylist Agent:
- Isabella Chen: high-net-worth Gucci loyalist, contemporary style
- James Crawford: collector and connoisseur, Louis Vuitton classic
- Sophie Laurent: fashion-forward eclectic, mixed luxury brands

Each profile is structured for CustomerProfile entity construction.
"""

from __future__ import annotations

CUSTOMER_PROFILES: list[dict] = [
    {
        "customer_id": "cust-isabella-chen-001",
        "tenant_id": "gucci",
        "preferences": {
            "preferred_brands": ["Gucci", "Bottega Veneta", "Saint Laurent"],
            "preferred_colours": ["dusty pink", "ivory", "emerald green"],
            "avoided_colours": ["neon", "orange"],
            "preferred_materials": ["silk", "leather", "cashmere"],
            "budget_range": "2000-5000 EUR",
            "communication_style": "warm and personal",
            "shopping_frequency": "monthly",
            "preferred_channel": "web",
            "gift_wrapping": True,
            "sustainability_conscious": True,
        },
        "style_tags": [
            "contemporary luxury",
            "feminine",
            "bold prints",
            "Italian craftsmanship",
            "evening wear",
            "statement accessories",
        ],
        "purchase_history_ids": [
            "order-gc-20240815-001",
            "order-gc-20241022-002",
            "order-gc-20241210-003",
            "order-gc-20250114-004",
        ],
        "wishlist_ids": [
            "GUCCI-BAG-001",
            "GUCCI-RTW-001",
        ],
        "size_profile": {
            "clothing_size": "S/M",
            "clothing_size_it": "42",
            "shoe_size_eu": "38",
            "ring_size": "52",
            "belt_size": "75 cm",
        },
        "preferred_locale": {"language": "en", "region": ""},
        "conversation_count": 7,
    },
    {
        "customer_id": "cust-james-crawford-002",
        "tenant_id": "louis-vuitton",
        "preferences": {
            "preferred_brands": ["Louis Vuitton", "Berluti", "Loro Piana"],
            "preferred_colours": ["navy", "brown", "charcoal", "black"],
            "avoided_colours": ["pink", "pastel"],
            "preferred_materials": ["leather", "canvas", "cashmere", "wool"],
            "budget_range": "1500-8000 EUR",
            "communication_style": "concise and knowledgeable",
            "shopping_frequency": "quarterly",
            "preferred_channel": "web",
            "collector": True,
            "interested_in_limited_editions": True,
            "monogram_preference": "classic Monogram",
        },
        "style_tags": [
            "classic luxury",
            "heritage",
            "travel essential",
            "timeless elegance",
            "collector pieces",
            "understated masculinity",
        ],
        "purchase_history_ids": [
            "order-lv-20230512-001",
            "order-lv-20231124-002",
            "order-lv-20240305-003",
            "order-lv-20240821-004",
            "order-lv-20241109-005",
            "order-lv-20250201-006",
        ],
        "wishlist_ids": [
            "LV-BAG-002",
            "LV-BAG-003",
        ],
        "size_profile": {
            "clothing_size": "L",
            "clothing_size_it": "50",
            "shoe_size_eu": "43",
            "belt_size": "95 cm",
        },
        "preferred_locale": {"language": "en", "region": "GB"},
        "conversation_count": 12,
    },
    {
        "customer_id": "cust-sophie-laurent-003",
        "tenant_id": "burberry",
        "preferences": {
            "preferred_brands": ["Burberry", "Gucci", "Loewe", "Acne Studios"],
            "preferred_colours": ["black", "archive beige", "forest green", "burgundy"],
            "avoided_colours": [],
            "preferred_materials": ["leather", "cashmere", "gabardine", "silk"],
            "budget_range": "500-3000 EUR",
            "communication_style": "creative and exploratory",
            "shopping_frequency": "bi-monthly",
            "preferred_channel": "mobile_app",
            "interested_in_new_arrivals": True,
            "interested_in_runway_pieces": True,
            "open_to_suggestions": True,
        },
        "style_tags": [
            "avant-garde",
            "fashion-forward",
            "British heritage remix",
            "layering expert",
            "pattern mixing",
            "gender-fluid style",
        ],
        "purchase_history_ids": [
            "order-bb-20240603-001",
            "order-bb-20241019-002",
            "order-bb-20250106-003",
        ],
        "wishlist_ids": [
            "BURB-RTW-001",
            "BURB-BAG-002",
            "BURB-ACC-001",
        ],
        "size_profile": {
            "clothing_size": "M",
            "clothing_size_it": "44",
            "clothing_size_fr": "38",
            "shoe_size_eu": "39",
            "scarf_preference": "oversized",
        },
        "preferred_locale": {"language": "fr", "region": "FR"},
        "conversation_count": 4,
    },
]
"""
Customer profiles for the PRISM demo stylist agent.

Each profile provides rich ContextOps data that the AI agent uses
to personalise recommendations and conversation style.
"""


def get_customer_for_tenant(tenant_id: str) -> dict | None:
    """
    Return the first customer profile matching the given tenant.

    Args:
        tenant_id: The tenant identifier.

    Returns:
        Customer profile dict, or None if no match found.
    """
    for profile in CUSTOMER_PROFILES:
        if profile["tenant_id"] == tenant_id:
            return profile
    return None


def get_customer_by_id(customer_id: str) -> dict | None:
    """
    Return a customer profile by its customer_id.

    Args:
        customer_id: The customer identifier.

    Returns:
        Customer profile dict, or None if not found.
    """
    for profile in CUSTOMER_PROFILES:
        if profile["customer_id"] == customer_id:
            return profile
    return None
