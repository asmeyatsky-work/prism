"""
PRISM Demo API — FastAPI Application

A fully wired demo server that composes mock infrastructure adapters with
real domain use cases. Seeds the catalogue with luxury product data on startup
and exposes REST endpoints spanning all six PRISM bounded contexts.

Endpoints:
    POST /api/catalogue/ingest          — Ingest a product (or batch)
    GET  /api/catalogue/products        — List products (tenant-scoped)
    GET  /api/catalogue/products/{id}   — Get product detail
    POST /api/intelligence/enrich/{id}  — Trigger AI enrichment
    POST /api/discovery/search          — Multimodal search
    POST /api/tryon/process             — Virtual try-on
    POST /api/payment/process           — Process a payment
    POST /api/agent/conversation        — Start a conversation
    POST /api/agent/conversation/{id}/message — Send message to agent
    GET  /api/agent/conversation/{id}   — Get conversation state
    GET  /api/health                    — Health check
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pathlib import Path

import hashlib

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from prism.catalogue.application.commands.ingest_product import (
    IngestProductCommand,
    IngestProductUseCase,
)
from prism.catalogue.application.dtos.product_dto import ProductDTO, ProductSummaryDTO
from prism.shared.infrastructure.event_bus import InMemoryEventBus

from prism.demo.mocks.catalogue_mocks import InMemoryProductRepository
from prism.demo.mocks.discovery_mocks import (
    MockHybridSearch,
    MockImageSearch,
    MockPersonalisation,
    MockVectorSearch,
)
from prism.demo.mocks.intelligence_mocks import (
    MockAttributeExtractor,
    MockDescriptionGenerator,
    MockEmbeddingGenerator,
    MockImageQuality,
    MockVectorIndex,
)
from prism.demo.mocks.tryon_mocks import MockBodyExtractor, MockCompositor
from prism.demo.mocks.payment_mocks import (
    MockFXRate,
    InMemoryPaymentRepository,
    MockPSP,
    MockRoutingRuleRepository,
)
from prism.demo.mocks.agentic_cx_mocks import (
    MockAgentLLM,
    InMemoryConversationRepository,
    MockCustomerProfile,
    MockSessionMemory,
    MockToolExecutor,
)

from prism.demo.seed_data.luxury_products import LUXURY_PRODUCTS
from prism.demo.seed_data.brands import BRANDS
from prism.demo.seed_data.customers import CUSTOMER_PROFILES

logger = logging.getLogger("prism.demo")

# ---------------------------------------------------------------------------
# Request / response models for the API layer
# ---------------------------------------------------------------------------


class BatchIngestRequest(BaseModel):
    """Request body for batch product ingestion."""

    products: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of product dicts to ingest",
    )


class SearchRequest(BaseModel):
    """Request body for product search."""

    query_text: str | None = None
    image_uri: str | None = None
    modality: str = "TEXT"
    filters: dict[str, str | list[str]] = Field(default_factory=dict)
    top_k: int = Field(default=20, ge=1, le=100)
    customer_id: str | None = None


class TryOnRequest(BaseModel):
    """Request body for virtual try-on (demo variant without real image bytes)."""

    product_id: str
    category: str = "APPAREL"
    consent: bool = True
    background_preset: str = "studio_white"
    lighting_preset: str = "soft_diffused"


class PaymentRequest(BaseModel):
    """Request body for payment processing."""

    order_id: str = Field(default_factory=lambda: f"ORD-{uuid4().hex[:8].upper()}")
    amount: float = Field(gt=0)
    currency: str = "EUR"
    customer_currency: str = "EUR"
    settlement_currency: str = "EUR"
    card_token: str = "tok_demo_visa_4242"
    card_type: str = "visa"
    customer_id: str = ""


class StartConversationRequest(BaseModel):
    """Request body for starting a new agent conversation."""

    agent_type: str = "PERSONAL_STYLIST"
    channel: str = "WEB"
    customer_id: str = ""
    initial_message: str = ""


class SendMessageRequest(BaseModel):
    """Request body for sending a message in a conversation."""

    message: str
    modality: str = "TEXT"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "0.1.0-demo"
    timestamp: datetime
    catalogue_size: int = 0
    tenants: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Application state — holds all wired use cases and mock adapters
# ---------------------------------------------------------------------------


class _DemoState:
    """
    Holds all mock adapters and use case instances for the demo.

    Created once during application startup and attached to the FastAPI
    app.state for access in route handlers.
    """

    def __init__(self) -> None:
        # Shared infrastructure
        self.event_bus = InMemoryEventBus()

        # --- Catalogue context ---
        self.product_repo = InMemoryProductRepository()
        self.ingest_use_case = IngestProductUseCase(
            product_repository=self.product_repo,
            event_bus=self.event_bus,
        )

        # --- Discovery context ---
        self.vector_search = MockVectorSearch()
        self.image_search = MockImageSearch()
        self.hybrid_search = MockHybridSearch()
        self.personalisation = MockPersonalisation()

        # --- Intelligence context ---
        self.attribute_extractor = MockAttributeExtractor()
        self.description_generator = MockDescriptionGenerator()
        self.embedding_generator = MockEmbeddingGenerator()
        self.vector_index = MockVectorIndex()
        self.image_quality = MockImageQuality()

        # --- Try-on context ---
        self.body_extractor = MockBodyExtractor()
        self.compositor = MockCompositor()

        # --- Payment context ---
        self.psp = MockPSP()
        self.fx_provider = MockFXRate()
        self.routing_repo = MockRoutingRuleRepository()
        self.payment_repo = InMemoryPaymentRepository()

        # --- Agentic CX context ---
        self.conversation_repo = InMemoryConversationRepository()
        self.customer_profile_port = MockCustomerProfile()
        self.session_memory = MockSessionMemory()
        self.agent_llm = MockAgentLLM()
        self.tool_executor = MockToolExecutor()

    async def seed_catalogue(self) -> None:
        """Seed the product catalogue with luxury demo products."""
        logger.info("Seeding catalogue with %d luxury products...", len(LUXURY_PRODUCTS))
        success_count = 0
        for product_data in LUXURY_PRODUCTS:
            command = IngestProductCommand(**product_data)
            result = await self.ingest_use_case.execute(command)
            if result.success:
                success_count += 1
                logger.debug("Ingested: %s — %s", product_data["sku"], product_data["name"])
            else:
                logger.warning(
                    "Failed to ingest %s: %s", product_data["sku"], result.error
                )
        logger.info(
            "Catalogue seeded: %d/%d products ingested successfully.",
            success_count,
            len(LUXURY_PRODUCTS),
        )

    async def seed_customer_profiles(self) -> None:
        """Seed mock customer profiles for the stylist agent."""
        logger.info("Seeding %d customer profiles...", len(CUSTOMER_PROFILES))
        for profile_data in CUSTOMER_PROFILES:
            await self.customer_profile_port.seed_profile(profile_data)
        logger.info("Customer profiles seeded successfully.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """
    Create and configure the PRISM demo FastAPI application.

    Returns:
        Fully configured FastAPI app with all routes, middleware, and
        seeded demo data.
    """
    state = _DemoState()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Seed data on startup, clean up on shutdown."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        )
        logger.info("Starting PRISM Demo Server...")
        await state.seed_catalogue()
        await state.seed_customer_profiles()
        app.state._seeded = True  # type: ignore[attr-defined]
        logger.info(
            "PRISM Demo Server ready. Explore the API at http://localhost:8000/docs"
        )
        yield
        logger.info("Shutting down PRISM Demo Server.")

    app = FastAPI(
        title="PRISM — Unified Commerce Intelligence Platform",
        description=(
            "Demo API for PRISM, a next-generation luxury retail platform combining "
            "AI-powered catalogue enrichment, multimodal search, virtual try-on, "
            "intelligent payment routing, and conversational AI styling."
        ),
        version="0.1.0-demo",
        lifespan=lifespan,
    )

    app.state.demo = state  # type: ignore[attr-defined]
    app.state._seeded = False  # type: ignore[attr-defined]

    @app.middleware("http")
    async def _lazy_seed(request: Request, call_next):
        """Seed on first request if lifespan hasn't run (e.g. httpx test client)."""
        if not request.app.state._seeded:
            request.app.state._seeded = True
            await state.seed_catalogue()
            await state.seed_customer_profiles()
        return await call_next(request)

    # CORS middleware for frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Helper: extract tenant context from request headers
    # ------------------------------------------------------------------

    def _tenant_id(x_tenant_id: str | None) -> str:
        return x_tenant_id or "gucci"

    def _get_state(request: Request) -> _DemoState:
        return request.app.state.demo  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Frontend
    # ------------------------------------------------------------------

    _static_dir = Path(__file__).parent.parent / "static"

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index() -> HTMLResponse:
        html = (_static_dir / "index.html").read_text()
        return HTMLResponse(content=html)

    # ------------------------------------------------------------------
    # Image proxy — serves external images through our own domain so
    # they load reliably regardless of client-side network restrictions.
    # ------------------------------------------------------------------

    _img_cache: dict[str, tuple[bytes, str]] = {}

    @app.get("/api/img", include_in_schema=False)
    async def proxy_image(url: str = Query(...)) -> Response:
        if not url.startswith("https://images.unsplash.com/"):
            raise HTTPException(status_code=400, detail="Only Unsplash URLs allowed")

        cache_key = hashlib.sha256(url.encode()).hexdigest()
        if cache_key in _img_cache:
            body, ct = _img_cache[cache_key]
            return Response(content=body, media_type=ct, headers={"Cache-Control": "public, max-age=86400"})

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError:
                raise HTTPException(status_code=502, detail="Failed to fetch image")

        body = resp.content
        ct = resp.headers.get("content-type", "image/jpeg")
        _img_cache[cache_key] = (body, ct)
        return Response(content=body, media_type=ct, headers={"Cache-Control": "public, max-age=86400"})

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.get(
        "/api/health",
        response_model=HealthResponse,
        tags=["System"],
        summary="Health check",
    )
    async def health_check(request: Request) -> HealthResponse:
        s = _get_state(request)
        return HealthResponse(
            status="healthy",
            timestamp=datetime.now(UTC),
            catalogue_size=s.product_repo.count_all(),
            tenants=[b["tenant_id"] for b in BRANDS],
        )

    # ------------------------------------------------------------------
    # Catalogue — Ingest
    # ------------------------------------------------------------------

    @app.post(
        "/api/catalogue/ingest",
        tags=["Catalogue"],
        summary="Ingest a single product or a batch of products",
    )
    async def ingest_product(
        request: Request,
        body: dict[str, Any] | list[dict[str, Any]] | BatchIngestRequest = None,  # type: ignore[assignment]
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> JSONResponse:
        s = _get_state(request)
        tenant = _tenant_id(x_tenant_id)

        # Normalise input: accept a single product dict, a list, or BatchIngestRequest
        raw_body = await request.json()
        products: list[dict[str, Any]]
        if isinstance(raw_body, list):
            products = raw_body
        elif isinstance(raw_body, dict) and "products" in raw_body:
            products = raw_body["products"]
        elif isinstance(raw_body, dict):
            products = [raw_body]
        else:
            raise HTTPException(status_code=400, detail="Invalid request body")

        results = []
        for product_data in products:
            product_data.setdefault("tenant_id", tenant)
            try:
                command = IngestProductCommand(**product_data)
            except Exception as exc:
                results.append({"sku": product_data.get("sku", "unknown"), "success": False, "error": str(exc)})
                continue

            result = await s.ingest_use_case.execute(command)
            if result.success and result.value is not None:
                results.append({
                    "sku": product_data["sku"],
                    "success": True,
                    "product_id": result.value.id,
                    "quality_score": result.value.quality_score,
                })
            else:
                results.append({
                    "sku": product_data.get("sku", "unknown"),
                    "success": False,
                    "error": result.error,
                })

        return JSONResponse(
            content={
                "total": len(products),
                "succeeded": sum(1 for r in results if r.get("success")),
                "failed": sum(1 for r in results if not r.get("success")),
                "results": results,
            },
            status_code=200,
        )

    # ------------------------------------------------------------------
    # Catalogue — List products
    # ------------------------------------------------------------------

    @app.get(
        "/api/catalogue/products",
        tags=["Catalogue"],
        summary="List all products for a tenant",
    )
    async def list_products(
        request: Request,
        offset: int = 0,
        limit: int = 50,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> JSONResponse:
        s = _get_state(request)
        tenant = _tenant_id(x_tenant_id)

        from prism.shared.domain.value_objects import TenantId

        tenant_id = TenantId(value=tenant)
        products, total = await s.product_repo.list_by_tenant(
            tenant_id, offset=offset, limit=limit
        )

        summaries = [ProductSummaryDTO.from_domain(p).model_dump(mode="json") for p in products]
        return JSONResponse(
            content={
                "tenant_id": tenant,
                "products": summaries,
                "total_count": total,
                "offset": offset,
                "limit": limit,
            }
        )

    # ------------------------------------------------------------------
    # Catalogue — Get product detail
    # ------------------------------------------------------------------

    @app.get(
        "/api/catalogue/products/{product_id}",
        tags=["Catalogue"],
        summary="Get product detail by ID",
    )
    async def get_product(
        request: Request,
        product_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> JSONResponse:
        s = _get_state(request)
        tenant = _tenant_id(x_tenant_id)

        from prism.shared.domain.value_objects import TenantId

        tenant_id = TenantId(value=tenant)
        product = await s.product_repo.get_by_id(product_id, tenant_id)
        if product is None:
            # Fallback: search all tenants (demo convenience)
            product = s.product_repo.get_by_id_any_tenant(product_id)

        if product is None:
            raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

        dto = ProductDTO.from_domain(product)
        return JSONResponse(content=dto.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Intelligence — Enrich product
    # ------------------------------------------------------------------

    @app.post(
        "/api/intelligence/enrich/{product_id}",
        tags=["Intelligence"],
        summary="Trigger AI enrichment for a product",
    )
    async def enrich_product(
        request: Request,
        product_id: str,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> JSONResponse:
        s = _get_state(request)
        tenant = _tenant_id(x_tenant_id)

        from prism.shared.domain.value_objects import TenantId

        tenant_id = TenantId(value=tenant)
        product = await s.product_repo.get_by_id(product_id, tenant_id)
        if product is None:
            product = s.product_repo.get_by_id_any_tenant(product_id)

        if product is None:
            raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")

        # Simulate enrichment: extract attributes via mock, generate description
        extracted = await s.attribute_extractor.extract_attributes(
            images=list(product.images),
            context={"brand": product.brand, "category": product.category},
        )

        from prism.intelligence.domain.value_objects.model_config import BrandVoiceConfig, Tone

        voice_config = BrandVoiceConfig(
            brand_name=product.brand,
            tone=Tone.LUXURY,
            style_guidelines="Elegant luxury prose",
            example_descriptions=(),
        )
        from prism.shared.domain.value_objects import Locale

        description = await s.description_generator.generate_description(
            attributes=extracted.to_flat_dict() if hasattr(extracted, "to_flat_dict") else {},
            voice_config=voice_config,
            locale=Locale(language="en", region="GB"),
        )
        embedding = await s.embedding_generator.generate_text_embedding(
            text=product.description or product.name,
        )
        image_quality_score = await s.image_quality.assess_quality(list(product.images))
        vector_id = await s.vector_index.upsert(
            product_id=product.id,
            vector=embedding,
        )

        # Apply enrichment to the product aggregate
        enriched_attrs = extracted.to_flat_dict() if hasattr(extracted, "to_flat_dict") else {}
        enriched_attrs["ai_description"] = (
            description.text if hasattr(description, "text") else str(description)
        )
        enriched_product = product.enrich(enriched_attrs)
        enriched_product = enriched_product.update_quality_score(
            min(1.0, product.quality_score + 0.3)
        )

        from dataclasses import replace as dc_replace

        enriched_product = dc_replace(enriched_product, embedding_vector_id=vector_id)
        await s.product_repo.save(enriched_product)

        dto = ProductDTO.from_domain(enriched_product)
        return JSONResponse(
            content={
                "status": "enriched",
                "product_id": product_id,
                "enrichment_status": dto.enrichment_status,
                "quality_score": dto.quality_score,
                "enriched_attributes": enriched_attrs,
                "embedding_vector_id": vector_id,
                "image_quality_score": image_quality_score,
                "product": dto.model_dump(mode="json"),
            }
        )

    # ------------------------------------------------------------------
    # Discovery — Search
    # ------------------------------------------------------------------

    @app.post(
        "/api/discovery/search",
        tags=["Discovery"],
        summary="Search products via text, image, or hybrid modality",
    )
    async def search_products(
        request: Request,
        body: SearchRequest,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> JSONResponse:
        s = _get_state(request)
        tenant = _tenant_id(x_tenant_id)

        from prism.discovery.application.dtos.search_dto import SearchRequestDTO

        search_request = SearchRequestDTO(
            tenant_id=tenant,
            query_text=body.query_text,
            image_uri=body.image_uri,
            modality=body.modality,
            filters=body.filters,
            top_k=body.top_k,
            customer_id=body.customer_id,
        )

        from prism.discovery.application.commands.execute_search import ExecuteSearchUseCase

        use_case = ExecuteSearchUseCase(
            vector_search=s.vector_search,
            image_search=s.image_search,
            hybrid_search=s.hybrid_search,
            personalisation=s.personalisation,
        )
        result = await use_case.execute(search_request)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        response_dto = result.value
        # Enrich results with product details from catalogue
        enriched_results = []
        for search_result in response_dto.results:
            product = s.product_repo.get_by_id_any_tenant(search_result.product_id)
            product_summary = None
            if product:
                summary_dto = ProductSummaryDTO.from_domain(product)
                product_summary = summary_dto.model_dump(mode="json")

            enriched_results.append({
                "product_id": search_result.product_id,
                "score": round(search_result.score, 4),
                "rank": search_result.rank,
                "explanation": search_result.explanation,
                "product": product_summary,
            })

        return JSONResponse(
            content={
                "session_id": response_dto.session_id,
                "modality": response_dto.modality,
                "total_count": response_dto.total_count,
                "query_time_ms": round(response_dto.query_time_ms, 2),
                "results": enriched_results,
            }
        )

    # ------------------------------------------------------------------
    # Try-On — Process
    # ------------------------------------------------------------------

    @app.post(
        "/api/tryon/process",
        tags=["Virtual Try-On"],
        summary="Process a virtual try-on request",
    )
    async def process_tryon(
        request: Request,
        body: TryOnRequest,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> JSONResponse:
        s = _get_state(request)
        tenant = _tenant_id(x_tenant_id)

        from prism.shared.domain.value_objects import TenantId, ImageRef

        # Find product to get its image
        product = s.product_repo.get_by_id_any_tenant(body.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail=f"Product not found: {body.product_id}")

        product_image = product.images[0] if product.images else ImageRef(
            bucket="prism-demo", path="placeholder.jpg"
        )

        from prism.tryon.application.dtos.tryon_dto import TryOnRequestDTO
        from prism.tryon.application.commands.process_tryon import ProcessTryOnUseCase

        # In demo mode, we provide synthetic customer image bytes
        demo_customer_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128  # synthetic placeholder

        tryon_request = TryOnRequestDTO(
            customer_image=demo_customer_image,
            product_id=body.product_id,
            tenant_id=tenant,
            consent=body.consent,
            category=body.category,
            background_preset=body.background_preset,
            lighting_preset=body.lighting_preset,
        )

        use_case = ProcessTryOnUseCase(
            body_extractor=s.body_extractor,
            compositor=s.compositor,
        )
        result = await use_case.execute(tryon_request, product_image)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        return JSONResponse(
            content={
                "session_id": result.value.session_id,
                "product_id": result.value.product_id,
                "result_image_url": result.value.result_image_url,
                "confidence": result.value.confidence,
                "processing_time_ms": result.value.processing_time_ms,
                "within_latency_budget": result.value.within_latency_budget,
                "product_name": product.name,
                "product_brand": product.brand,
            }
        )

    # ------------------------------------------------------------------
    # Payment — Process
    # ------------------------------------------------------------------

    @app.post(
        "/api/payment/process",
        tags=["Payment"],
        summary="Process a payment through FlowRoute",
    )
    async def process_payment(
        request: Request,
        body: PaymentRequest,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> JSONResponse:
        s = _get_state(request)
        tenant = _tenant_id(x_tenant_id)

        from prism.payment.application.dtos.payment_dto import PaymentRequestDTO
        from prism.payment.application.commands.process_payment import ProcessPaymentUseCase
        from prism.payment.domain.value_objects.routing import PSPCapability

        payment_request = PaymentRequestDTO(
            order_id=body.order_id,
            tenant_id=tenant,
            amount=body.amount,
            currency=body.currency,
            customer_currency=body.customer_currency,
            settlement_currency=body.settlement_currency,
            card_token=body.card_token,
            card_type=body.card_type,
            customer_id=body.customer_id,
        )

        use_case = ProcessPaymentUseCase(
            psp_registry={
                "stripe_eu": s.psp,
                "planet_apac": MockPSP(psp_name="planet_apac"),
                "adyen_global": MockPSP(psp_name="adyen_global"),
            },
            fx_providers=[s.fx_provider],
            routing_rule_repo=s.routing_repo,
            payment_repo=s.payment_repo,
            psp_capabilities=[],
            event_bus=s.event_bus,
        )
        result = await use_case.execute(payment_request)

        if not result.success:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": result.error,
                    "error_code": result.error_code,
                },
            )

        return JSONResponse(
            content={
                "success": True,
                "payment_id": result.value.payment_id,
                "order_id": result.value.order_id,
                "status": result.value.status,
                "amount": result.value.amount,
                "currency": result.value.currency,
                "psp_id": result.value.psp_id,
                "psp_transaction_id": result.value.psp_transaction_id,
            }
        )

    # ------------------------------------------------------------------
    # Agentic CX — Start Conversation
    # ------------------------------------------------------------------

    @app.post(
        "/api/agent/conversation",
        tags=["Agentic CX"],
        summary="Start a new conversation with the AI stylist",
    )
    async def start_conversation(
        request: Request,
        body: StartConversationRequest,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> JSONResponse:
        s = _get_state(request)
        tenant = _tenant_id(x_tenant_id)

        from prism.agentic_cx.application.dtos.agent_dto import StartConversationRequestDTO
        from prism.agentic_cx.application.commands.start_conversation import (
            StartConversationUseCase,
        )

        start_request = StartConversationRequestDTO(
            tenant_id=tenant,
            agent_type=body.agent_type,
            channel=body.channel,
            customer_id=body.customer_id,
            initial_message=body.initial_message,
        )

        use_case = StartConversationUseCase(
            conversation_repo=s.conversation_repo,
            customer_profile_port=s.customer_profile_port,
            session_memory=s.session_memory,
            event_bus=s.event_bus,
        )
        result = await use_case.execute(start_request)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        conversation_dto = result.value
        return JSONResponse(
            content=conversation_dto.model_dump(mode="json"),
            status_code=201,
        )

    # ------------------------------------------------------------------
    # Agentic CX — Send Message
    # ------------------------------------------------------------------

    @app.post(
        "/api/agent/conversation/{conversation_id}/message",
        tags=["Agentic CX"],
        summary="Send a message to the AI stylist",
    )
    async def send_message(
        request: Request,
        conversation_id: str,
        body: SendMessageRequest,
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> JSONResponse:
        s = _get_state(request)

        from prism.agentic_cx.application.dtos.agent_dto import SendMessageRequestDTO
        from prism.agentic_cx.application.commands.handle_message import HandleMessageUseCase
        from prism.agentic_cx.domain.entities.agent_persona import AgentPersona, PersonaTone
        from prism.agentic_cx.domain.value_objects.agent_config import AgentToolkit

        # Find the brand config for tone
        tenant = _tenant_id(x_tenant_id)
        brand_config = next((b for b in BRANDS if b["tenant_id"] == tenant), BRANDS[0])

        persona = AgentPersona(
            tenant_id=tenant,
            brand_name=brand_config["name"],
            persona_name="Aria",
            tone=PersonaTone.LUXURY,
            greeting_template=(
                f"Welcome to {brand_config['name']}. I'm Aria, your personal stylist. "
                "How may I assist you today?"
            ),
            style_guidelines=brand_config["tone_profile"],
            escalation_threshold=0.3,
        )

        toolkit = AgentToolkit(
            available_tools=(
                "catalogue_search",
                "virtual_tryon",
                "inventory_check",
                "wishlist_manage",
                "appointment_book",
            )
        )

        send_request = SendMessageRequestDTO(
            conversation_id=conversation_id,
            content=body.message,
            modality=body.modality,
        )

        use_case = HandleMessageUseCase(
            conversation_repo=s.conversation_repo,
            customer_profile_port=s.customer_profile_port,
            session_memory=s.session_memory,
            agent_llm=s.agent_llm,
            tool_executor=s.tool_executor,
            event_bus=s.event_bus,
            persona=persona,
            toolkit=toolkit,
        )
        result = await use_case.execute(send_request)

        if not result.success:
            raise HTTPException(status_code=400, detail=result.error)

        response_dto = result.value
        return JSONResponse(
            content=response_dto.model_dump(mode="json"),
        )

    # ------------------------------------------------------------------
    # Agentic CX — Get Conversation
    # ------------------------------------------------------------------

    @app.get(
        "/api/agent/conversation/{conversation_id}",
        tags=["Agentic CX"],
        summary="Get conversation state and history",
    )
    async def get_conversation(
        request: Request,
        conversation_id: str,
    ) -> JSONResponse:
        s = _get_state(request)

        conversation = await s.conversation_repo.get_by_id(conversation_id)
        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail=f"Conversation not found: {conversation_id}",
            )

        from prism.agentic_cx.application.dtos.agent_dto import ConversationDTO, MessageDTO

        messages = [
            MessageDTO(
                role=m.role.value,
                content=m.content,
                modality=m.modality.value,
                timestamp=m.timestamp,
                metadata=m.metadata,
            )
            for m in conversation.messages
        ]
        dto = ConversationDTO(
            conversation_id=conversation.conversation_id,
            tenant_id=conversation.tenant_id,
            customer_id=conversation.customer_id,
            agent_type=conversation.agent_type.value,
            channel=conversation.channel.value,
            status=conversation.status.value,
            messages=messages,
            started_at=conversation.started_at,
            last_activity_at=conversation.last_activity_at,
        )

        return JSONResponse(content=dto.model_dump(mode="json"))

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc),
                "type": type(exc).__name__,
            },
        )

    return app
