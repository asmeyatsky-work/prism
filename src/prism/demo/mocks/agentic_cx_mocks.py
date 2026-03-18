"""
Agentic CX Context — Mock Agent, Tool, Memory, and Channel Adapters

Provides mock implementations of:
- AgentLLMPort              -> MockAgentLLM
- ToolExecutionPort         -> MockToolExecutor
- ConversationRepositoryPort -> InMemoryConversationRepository
- CustomerProfilePort       -> MockCustomerProfile
- SessionMemoryPort         -> MockSessionMemory
- LongTermMemoryPort        -> MockLongTermMemory
- ChannelAdapterPort        -> MockChannelAdapter

MockAgentLLM returns pre-scripted luxury personal shopper responses
based on keyword detection, creating a convincing demo experience.
"""

from __future__ import annotations

import logging
import random
from typing import Any

from prism.agentic_cx.domain.entities.conversation import Conversation
from prism.agentic_cx.domain.entities.customer_profile import CustomerProfile
from prism.agentic_cx.domain.value_objects.agent_config import Channel
from prism.shared.domain.value_objects import Locale

logger = logging.getLogger("prism.demo.agentic_cx")


# ── Pre-scripted luxury stylist responses ──────────────────────────────

_GREETING_RESPONSES = [
    (
        "Welcome back to {brand}. I'm your personal stylist and I'm delighted "
        "to assist you today. Whether you're looking for something specific or "
        "simply seeking inspiration, I'm here to curate the perfect selection "
        "for you. How may I help?"
    ),
    (
        "Good day, and thank you for choosing {brand}. As your dedicated "
        "stylist, I have access to our complete collection and can arrange "
        "virtual try-ons, check availability worldwide, and coordinate "
        "personal shopping appointments. What brings you in today?"
    ),
]

_DRESS_RESPONSES = [
    (
        "I'd be delighted to help you find the perfect dress. Based on your "
        "style profile, I think you'd love our new Valentino Garavani Cady "
        "Couture Evening Gown -- it's an extraordinary piece in flowing silk "
        "crepe with a dramatic train, perfect for black-tie occasions. We also "
        "have the Gucci Flora Print Silk Dress, which offers a more "
        "contemporary silhouette for gallery openings or cocktail receptions.\n\n"
        "Shall I pull up these options with detailed imagery, or would you "
        "prefer to explore a specific occasion or colour palette?"
    ),
    (
        "For dresses, our current collection features some truly exceptional "
        "pieces. The Valentino couture evening gown in Nero is generating "
        "significant interest -- only four remain in our Paris atelier. For "
        "something more versatile, the Gucci Flora silk dress transitions "
        "beautifully from day to evening.\n\n"
        "I can also arrange a virtual try-on so you can see how each piece "
        "drapes. Would you like me to set that up?"
    ),
]

_BAG_RESPONSES = [
    (
        "Handbags are one of my favourite categories to curate. Let me share "
        "some standout pieces from our collection:\n\n"
        "The **Hermes Birkin 30 in Togo Leather** -- truly the pinnacle of "
        "luxury leather goods. We have just two available, both in our Paris "
        "Faubourg boutique.\n\n"
        "The **Gucci Diana Mini Tote** -- a reimagined archival design with "
        "the iconic bamboo handle. Versatile enough for daily use while making "
        "a distinct statement.\n\n"
        "The **Bottega Veneta Cassette** in Intrecciato -- for those who "
        "appreciate quiet luxury and masterful craftsmanship.\n\n"
        "Which aesthetic speaks to you? I can check real-time availability "
        "and arrange viewing at your nearest boutique."
    ),
    (
        "I have some wonderful suggestions for you. Our Chanel Classic Flap "
        "in medium is one of the most requested pieces this season -- only "
        "three remain at Rue Cambon. The Prada Galleria in Saffiano leather "
        "is another exquisite option for the woman who values architectural "
        "elegance.\n\n"
        "For something more contemporary, the Dior Saddle Bag in Oblique "
        "jacquard offers a bold statement piece that photographs beautifully.\n\n"
        "Would you like to see these in detail, or shall I refine based on "
        "a particular colour or size preference?"
    ),
]

_GIFT_RESPONSES = [
    (
        "How wonderful that you're selecting a gift. Allow me to curate a "
        "thoughtful selection based on the occasion:\n\n"
        "**For Her:**\n"
        "- Hermes Carre 90 Silk Scarf -- a timeless gesture of elegance, "
        "beautifully presented in the iconic orange box\n"
        "- Tiffany & Co. Elsa Peretti Open Heart Pendant -- a romantic "
        "classic that transcends trends\n\n"
        "**Accessories:**\n"
        "- Celine Triomphe Belt in smooth calfskin -- sophisticated and "
        "practical, a gift they'll reach for every day\n"
        "- Cartier Tank Francaise Watch -- an investment piece that speaks "
        "volumes about your taste\n\n"
        "I can also arrange complimentary gift wrapping with a personalised "
        "message card. Shall I check availability for any of these?"
    ),
    (
        "Finding the perfect gift is an art, and I'm here to make it "
        "effortless. A few of my personal recommendations:\n\n"
        "The **Hermes silk scarf** is always a flawless choice -- it's "
        "universally appreciated and arrives in that unmistakable packaging. "
        "For something with more presence, the **Cartier Tank Francaise** is "
        "a gift that becomes an heirloom.\n\n"
        "If you share a bit more about the recipient -- their style, the "
        "occasion, a budget range -- I can narrow down to the perfect piece."
    ),
]

_SHOE_RESPONSES = [
    (
        "For footwear, we have some exceptional options this season:\n\n"
        "The **Christian Louboutin Kate 100** in patent leather is the "
        "definitive evening pump -- that flash of red sole is unmistakable. "
        "For a more relaxed luxury look, the **Gucci Ace Embroidered Sneaker** "
        "is our most requested casual style.\n\n"
        "The **Louis Vuitton Archlight Sneaker** offers a fashion-forward "
        "silhouette that pairs beautifully with everything from tailored "
        "trousers to flowing midi dresses.\n\n"
        "Would you like me to check your size availability, or shall we "
        "explore a specific style direction?"
    ),
]

_OUTFIT_RESPONSES = [
    (
        "I'd love to put together a complete look for you. Let me suggest a "
        "few curated ensembles:\n\n"
        "**Evening Elegance:**\n"
        "Valentino evening gown + Louboutin Kate pumps + Chanel Classic Flap "
        "+ Tiffany pendant. Total look confidence score: 0.94.\n\n"
        "**Business Power:**\n"
        "Burberry Kensington trench + Prada Galleria bag + Cartier Tank watch "
        "+ Celine Triomphe belt. Effortlessly commanding.\n\n"
        "**Weekend Luxe:**\n"
        "Gucci Ace sneakers + Bottega Cassette bag + Hermes silk scarf. "
        "Casual without compromising on quality.\n\n"
        "I can run a virtual try-on for any of these combinations. Which "
        "resonates with your plans?"
    ),
]

_SIZE_RESPONSES = [
    (
        "Of course -- getting the fit right is essential. Based on your "
        "profile, you typically wear a {size_category}. I'd recommend:\n\n"
        "- For Italian designers (Gucci, Prada, Valentino): size {it_size}\n"
        "- For French houses (Chanel, Dior, Hermes): size {fr_size}\n\n"
        "I can also arrange a virtual fitting with our AI try-on technology "
        "to verify the drape and proportion before you commit. Would that "
        "be helpful?"
    ),
]

_AVAILABILITY_RESPONSES = [
    (
        "Let me check that for you right away.\n\n"
        "I can see the item is currently available at our {location} location "
        "with {quantity} units in stock. We offer both shipping and boutique "
        "collection.\n\n"
        "Given the limited availability, I'd recommend securing your piece "
        "promptly. Shall I reserve it for you, or would you prefer to see "
        "it in person first?"
    ),
]

_DEFAULT_RESPONSES = [
    (
        "Thank you for sharing that. Let me look into the best options for "
        "you from our current collection. I have access to our full catalogue, "
        "real-time inventory across all boutiques, and can arrange virtual "
        "try-ons or in-store appointments.\n\n"
        "Could you tell me a bit more about what you're looking for? For "
        "instance, the occasion, any preferred brands, or a style direction "
        "you're drawn to?"
    ),
    (
        "I appreciate you reaching out. To curate the most relevant selection, "
        "it would be wonderful to know:\n\n"
        "- Is this for a specific occasion?\n"
        "- Do you have any brand or material preferences?\n"
        "- Are you open to exploring new designers?\n\n"
        "I'm here to make the experience as seamless and enjoyable as a "
        "visit to one of our flagship boutiques."
    ),
]


def _detect_intent(text: str) -> str:
    """Simple keyword-based intent detection for demo routing."""
    text_lower = text.lower()

    keywords_map = {
        "dress": ["dress", "gown", "evening wear", "cocktail", "frock"],
        "bag": ["bag", "handbag", "purse", "tote", "clutch", "satchel", "crossbody"],
        "gift": ["gift", "present", "birthday", "anniversary", "surprise", "occasion"],
        "shoe": ["shoe", "boot", "sneaker", "pump", "heel", "loafer", "sandal"],
        "outfit": ["outfit", "look", "ensemble", "complete the look", "styling", "coordinate"],
        "size": ["size", "fit", "sizing", "measurement", "dimensions"],
        "availability": ["available", "stock", "in stock", "availability", "reserve"],
        "greeting": ["hello", "hi", "hey", "good morning", "good afternoon", "good evening", "help"],
    }

    for intent, keywords in keywords_map.items():
        if any(kw in text_lower for kw in keywords):
            return intent

    return "default"


class MockAgentLLM:
    """
    Mock LLM that returns pre-scripted luxury personal shopper responses
    based on keyword detection in the conversation context. Responses are
    crafted to feel like a genuine high-end retail concierge experience.
    """

    _RESPONSE_MAP: dict[str, list[str]] = {
        "greeting": _GREETING_RESPONSES,
        "dress": _DRESS_RESPONSES,
        "bag": _BAG_RESPONSES,
        "gift": _GIFT_RESPONSES,
        "shoe": _SHOE_RESPONSES,
        "outfit": _OUTFIT_RESPONSES,
        "size": _SIZE_RESPONSES,
        "availability": _AVAILABILITY_RESPONSES,
        "default": _DEFAULT_RESPONSES,
    }

    async def generate_response(
        self,
        context: dict[str, Any],
        tools: list[dict[str, Any]],
    ) -> str:
        # Extract the latest customer message from context
        messages = context.get("messages", [])
        latest_text = ""
        for msg in reversed(messages):
            if isinstance(msg, dict) and msg.get("role") in ("CUSTOMER", "customer"):
                latest_text = msg.get("content", "")
                break
            elif hasattr(msg, "role") and getattr(msg, "role", None) in ("CUSTOMER", "customer"):
                latest_text = getattr(msg, "content", "")
                break

        if not latest_text:
            latest_text = str(context.get("query", context.get("input", "")))

        intent = _detect_intent(latest_text)
        templates = self._RESPONSE_MAP.get(intent, _DEFAULT_RESPONSES)
        response = random.choice(templates)

        # Fill in template variables
        brand = context.get("brand", context.get("tenant_id", "the Maison"))
        response = response.replace("{brand}", str(brand))
        response = response.replace("{size_category}", "Medium / EU 38-40")
        response = response.replace("{it_size}", "42")
        response = response.replace("{fr_size}", "40")
        response = response.replace("{location}", "Milan Warehouse")
        response = response.replace("{quantity}", str(random.randint(2, 12)))

        return response


class MockToolExecutor:
    """
    Mock tool executor that dispatches to simplified mock implementations
    for catalogue search, try-on, and inventory tools.
    """

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        dispatch: dict[str, Any] = {
            "catalogue_search": self._catalogue_search,
            "virtual_tryon": self._virtual_tryon,
            "inventory_check": self._inventory_check,
            "wishlist_manage": self._wishlist_manage,
            "order_status": self._order_status,
        }

        handler = dispatch.get(tool_name)
        if handler is None:
            logger.warning("Unknown tool: %s", tool_name)
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not available in demo mode",
            }

        result = await handler(arguments)
        logger.info("Tool executed: %s -> %s", tool_name, result.get("status", "ok"))
        return result

    async def _catalogue_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query", "")
        return {
            "status": "success",
            "results": [
                {
                    "product_id": "prod_gucci_diana_001",
                    "name": "Gucci Diana Mini Tote Bag",
                    "price": "2,490.00 EUR",
                    "score": 0.94,
                },
                {
                    "product_id": "prod_hermes_birkin_004",
                    "name": "Hermes Birkin 30 Togo Leather",
                    "price": "9,800.00 EUR",
                    "score": 0.89,
                },
                {
                    "product_id": "prod_chanel_classic_007",
                    "name": "Chanel Classic Flap Bag Medium",
                    "price": "8,200.00 EUR",
                    "score": 0.87,
                },
            ],
            "total_count": 3,
            "query": query,
        }

    async def _virtual_tryon(self, args: dict[str, Any]) -> dict[str, Any]:
        product_id = args.get("product_id", "unknown")
        return {
            "status": "success",
            "composition_url": (
                "https://storage.googleapis.com/prism-tryon-results-demo/"
                f"compositions/{product_id}_tryon.png"
            ),
            "confidence": 0.91,
            "product_id": product_id,
        }

    async def _inventory_check(self, args: dict[str, Any]) -> dict[str, Any]:
        product_id = args.get("product_id", "unknown")
        locations = [
            "Milan Warehouse", "Paris Atelier", "London Warehouse",
            "New York Vault", "Tokyo Boutique",
        ]
        return {
            "status": "success",
            "product_id": product_id,
            "available": True,
            "quantity": random.randint(1, 15),
            "location": random.choice(locations),
            "fulfilment_options": ["SHIP", "STORE_PICKUP"],
        }

    async def _wishlist_manage(self, args: dict[str, Any]) -> dict[str, Any]:
        action = args.get("action", "add")
        product_id = args.get("product_id", "unknown")
        return {
            "status": "success",
            "action": action,
            "product_id": product_id,
            "message": f"Product {product_id} {'added to' if action == 'add' else 'removed from'} wishlist",
        }

    async def _order_status(self, args: dict[str, Any]) -> dict[str, Any]:
        order_id = args.get("order_id", "ORD-DEMO-001")
        return {
            "status": "success",
            "order_id": order_id,
            "order_status": "SHIPPED",
            "tracking_number": "1Z999AA10123456784",
            "carrier": "DHL Express",
            "estimated_delivery": "2026-03-21",
            "items": [
                {"product_id": "prod_gucci_diana_001", "name": "Gucci Diana Mini Tote Bag"}
            ],
        }


class InMemoryConversationRepository:
    """
    In-memory conversation repository with ID and customer-based lookups.
    Only one active conversation per customer is maintained.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, Conversation] = {}
        # {(customer_id, tenant_id): conversation_id}
        self._active_by_customer: dict[tuple[str, str], str] = {}

    async def save(self, conversation: Conversation) -> None:
        self._by_id[conversation.conversation_id] = conversation

        # Track active conversations
        if conversation.status.value == "ACTIVE":
            key = (conversation.customer_id, conversation.tenant_id)
            self._active_by_customer[key] = conversation.conversation_id
        elif conversation.status.value in ("COMPLETED", "ESCALATED"):
            key = (conversation.customer_id, conversation.tenant_id)
            if self._active_by_customer.get(key) == conversation.conversation_id:
                del self._active_by_customer[key]

    async def get_by_id(self, conversation_id: str) -> Conversation | None:
        return self._by_id.get(conversation_id)

    async def get_active_by_customer(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> Conversation | None:
        key = (customer_id, tenant_id)
        conv_id = self._active_by_customer.get(key)
        if conv_id:
            return self._by_id.get(conv_id)
        return None


class MockCustomerProfile:
    """
    Returns a pre-built luxury shopper profile representing a high-value
    returning customer with established style preferences and purchase history.
    """

    _DEFAULT_PROFILE = CustomerProfile(
        customer_id="cust_vip_001",
        tenant_id="gucci",
        preferences={
            "preferred_brands": ["Gucci", "Hermes", "Bottega Veneta"],
            "preferred_materials": ["leather", "silk", "cashmere"],
            "preferred_colours": ["Nero", "Burgundy", "Ivory"],
            "budget_range": "premium",
            "communication_style": "formal",
            "shopping_motivation": "quality and exclusivity",
        },
        style_tags=(
            "timeless elegance",
            "quiet luxury",
            "investment dressing",
            "Italian craftsmanship",
            "day-to-night versatility",
        ),
        purchase_history_ids=(
            "ord_2024_001",
            "ord_2024_008",
            "ord_2025_002",
            "ord_2025_011",
            "ord_2025_017",
        ),
        wishlist_ids=(
            "prod_hermes_birkin_004",
            "prod_cartier_tank_016",
            "prod_valentino_gown_013",
        ),
        size_profile={
            "dress": "IT 42 / FR 40 / US 8",
            "shoes": "IT 38 / FR 38 / US 7.5",
            "tops": "IT 42 / FR 40 / US S-M",
            "ring": "52 EU / 6 US",
        },
        preferred_locale=Locale(language="en", region="GB"),
        conversation_count=12,
    )

    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], CustomerProfile] = {
            ("cust_vip_001", "gucci"): self._DEFAULT_PROFILE,
        }

    async def get_profile(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> CustomerProfile | None:
        key = (customer_id, tenant_id)
        if key in self._profiles:
            return self._profiles[key]

        # Return a sensible default profile for unknown customers
        return CustomerProfile(
            customer_id=customer_id,
            tenant_id=tenant_id,
            preferences={
                "communication_style": "friendly",
                "shopping_motivation": "discovery",
            },
            style_tags=("modern classic", "versatile"),
            preferred_locale=Locale(language="en"),
            conversation_count=0,
        )

    async def update_profile(self, profile: CustomerProfile) -> None:
        key = (profile.customer_id, profile.tenant_id)
        self._profiles[key] = profile

    async def seed_profile(self, profile_data: dict) -> None:
        """Seed a customer profile from a dict (demo convenience)."""
        profile = CustomerProfile(
            customer_id=profile_data.get("customer_id", "unknown"),
            tenant_id=profile_data.get("tenant_id", "gucci"),
            preferences=profile_data.get("preferences", {}),
            style_tags=tuple(profile_data.get("style_tags", ())),
            purchase_history_ids=tuple(profile_data.get("purchase_history_ids", ())),
            wishlist_ids=tuple(profile_data.get("wishlist_ids", ())),
            size_profile=profile_data.get("size_profile", {}),
            preferred_locale=Locale(
                language=profile_data.get("locale", "en").split("-")[0],
                region=profile_data.get("locale", "en").split("-")[1]
                if "-" in profile_data.get("locale", "en")
                else "",
            ),
            conversation_count=profile_data.get("conversation_count", 0),
        )
        await self.update_profile(profile)


class MockSessionMemory:
    """
    In-memory session memory using nested dicts.
    Keyed by session_id (conversation_id) and then by memory key.
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def store(self, session_id: str, key: str, value: Any) -> None:
        if session_id not in self._store:
            self._store[session_id] = {}
        self._store[session_id][key] = value

    async def retrieve(self, session_id: str, key: str) -> Any:
        return self._store.get(session_id, {}).get(key)

    async def get_session_context(self, session_id: str) -> dict[str, Any]:
        return dict(self._store.get(session_id, {}))

    async def clear_session(self, session_id: str) -> None:
        self._store.pop(session_id, None)


class MockLongTermMemory:
    """
    In-memory long-term customer preference store.
    Persists preferences across conversations for ContextOps enrichment.
    """

    def __init__(self) -> None:
        # {customer_id: {key: value}}
        self._store: dict[str, dict[str, Any]] = {}
        # Pre-seed with VIP customer preferences
        self._store["cust_vip_001"] = {
            "preferred_colors": ["Nero", "Burgundy", "Ivory"],
            "avoided_materials": ["synthetic", "polyester"],
            "preferred_silhouettes": ["tailored", "structured"],
            "favourite_designers": ["Alessandro Michele", "Daniel Lee"],
            "gift_occasions": ["anniversary (March)", "birthday (September)"],
            "preferred_boutiques": ["London New Bond Street", "Milan Via Montenapoleone"],
        }

    async def store_preference(
        self,
        customer_id: str,
        key: str,
        value: Any,
    ) -> None:
        if customer_id not in self._store:
            self._store[customer_id] = {}
        self._store[customer_id][key] = value

    async def get_preferences(self, customer_id: str) -> dict[str, Any]:
        return dict(self._store.get(customer_id, {}))

    async def delete_preference(self, customer_id: str, key: str) -> None:
        if customer_id in self._store:
            self._store[customer_id].pop(key, None)


class MockChannelAdapter:
    """
    Mock channel adapter that logs all messages sent through any channel.
    Useful for inspecting agent outputs during demo and testing.
    """

    def __init__(self) -> None:
        self._message_log: list[dict[str, Any]] = []

    async def send(
        self,
        channel: Channel,
        destination: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        entry = {
            "channel": channel.value,
            "destination": destination,
            "message": message,
            "metadata": metadata or {},
        }
        self._message_log.append(entry)
        logger.info(
            "[%s -> %s] %s",
            channel.value,
            destination,
            message[:120] + ("..." if len(message) > 120 else ""),
        )

    @property
    def message_log(self) -> list[dict[str, Any]]:
        """Access the complete message log for testing/inspection."""
        return list(self._message_log)

    @property
    def last_message(self) -> dict[str, Any] | None:
        """Access the most recent sent message."""
        return self._message_log[-1] if self._message_log else None
