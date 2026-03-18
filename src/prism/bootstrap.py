"""
PRISM Application Bootstrap — Composition Root

Architectural Intent:
- Single entry point for wiring all ports to infrastructure adapters
- Creates the DependencyContainer and registers all bounded-context bindings
- Registers all MCP servers in the MCPServerRegistry
- Returns a fully configured Starlette application ready to serve
- Per skill2026 Rule 4: all composition happens here, not in domain or application layers
"""

from __future__ import annotations

import logging
from typing import Any

from prism.shared.infrastructure.di_container import DependencyContainer
from prism.shared.infrastructure.mcp_registry import MCPServerConfig, MCPServerRegistry

from prism.gateway.domain.ports.gateway_ports import (
    APIKeyRepositoryPort,
    PIMConnectorPort,
    RateLimiterPort,
    TenantConfigPort,
    WebhookDispatchPort,
)
from prism.gateway.infrastructure.adapters.webhook_dispatcher import WebhookDispatcher
from prism.gateway.infrastructure.middleware.rate_limiter import (
    InMemoryRateLimiter,
    RedisRateLimiter,
)
from prism.gateway.presentation.api.router import create_gateway_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MCP Server Definitions
# ---------------------------------------------------------------------------

_MCP_SERVERS: tuple[MCPServerConfig, ...] = (
    MCPServerConfig(
        name="catalogue-service",
        module="prism.catalogue.infrastructure.mcp_servers.catalogue_server",
        description="Catalogue bounded context — product and brand management",
        tools=("ingest_product", "update_product", "enrich_product"),
        resources=("product://", "brand://"),
    ),
    MCPServerConfig(
        name="intelligence-service",
        module="prism.intelligence.infrastructure.mcp_servers.intelligence_server",
        description="Intelligence bounded context — AI enrichment and analytics",
        tools=("generate_description", "classify_product", "extract_attributes"),
        resources=("enrichment://",),
    ),
    MCPServerConfig(
        name="discovery-service",
        module="prism.discovery.infrastructure.mcp_servers.discovery_server",
        description="Discovery bounded context — search and recommendations",
        tools=("index_product", "search"),
        resources=("search://",),
    ),
    MCPServerConfig(
        name="tryon-service",
        module="prism.tryon.infrastructure.mcp_servers.tryon_server",
        description="Virtual Try-On bounded context — AR/AI try-on experiences",
        tools=("create_tryon_session", "generate_tryon_image"),
        resources=("tryon://",),
    ),
    MCPServerConfig(
        name="commerce-service",
        module="prism.commerce.infrastructure.mcp_servers.commerce_server",
        description="Commerce bounded context — cart, checkout, and order management",
        tools=("create_order", "update_cart", "apply_promotion"),
        resources=("order://", "cart://"),
    ),
    MCPServerConfig(
        name="payment-service",
        module="prism.payment.infrastructure.mcp_servers.payment_server",
        description="Payment bounded context — payment processing and tokenisation",
        tools=("process_payment", "refund_payment", "tokenise_card"),
        resources=("payment://", "transaction://"),
    ),
    MCPServerConfig(
        name="agentic-cx-service",
        module="prism.agentic_cx.infrastructure.mcp_servers.agentic_cx_server",
        description="Agentic CX bounded context — AI-powered customer experience",
        tools=("start_conversation", "route_intent", "handoff_to_human"),
        resources=("conversation://",),
    ),
)


# ---------------------------------------------------------------------------
# Bootstrap Functions
# ---------------------------------------------------------------------------


def create_dependency_container(
    redis_client: Any | None = None,
) -> DependencyContainer:
    """
    Create and configure the DependencyContainer with all port -> adapter bindings.

    Args:
        redis_client: Optional Redis client. If None, in-memory adapters are used
                      (suitable for development and testing).

    Returns:
        Fully wired DependencyContainer.
    """
    container = DependencyContainer()

    # -- Rate Limiter --
    if redis_client is not None:
        rate_limiter = RedisRateLimiter(redis_client=redis_client)
    else:
        rate_limiter = InMemoryRateLimiter()
    container.register_singleton(RateLimiterPort, rate_limiter)  # type: ignore[type-abstract]

    logger.info(
        "Rate limiter registered: %s", type(rate_limiter).__name__
    )

    return container


def create_mcp_registry() -> MCPServerRegistry:
    """
    Create and populate the MCP server registry with all bounded-context servers.

    Returns:
        MCPServerRegistry with all PRISM MCP servers registered.
    """
    registry = MCPServerRegistry()

    for server_config in _MCP_SERVERS:
        registry.register(server_config)
        logger.info("MCP server registered: %s", server_config.name)

    logger.info(
        "MCP registry initialised with %d servers", len(_MCP_SERVERS)
    )

    return registry


def bootstrap(
    redis_client: Any | None = None,
    key_repository: APIKeyRepositoryPort | None = None,
    tenant_config_port: TenantConfigPort | None = None,
    context_routes: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    """
    Full application bootstrap — creates all infrastructure and returns the configured app.

    This is the main entry point for starting the PRISM platform. It:
    1. Creates the DependencyContainer with all port -> adapter bindings.
    2. Registers all MCP servers in the MCPServerRegistry.
    3. Builds the Gateway Starlette application with middleware and routes.

    Args:
        redis_client: Optional Redis async client for production rate limiting.
        key_repository: API key repository implementation. Required for production.
        tenant_config_port: Tenant config port implementation. Required for production.
        context_routes: Mapping of bounded-context name -> Starlette routes.

    Returns:
        Dictionary containing:
        - "app": The configured Starlette application.
        - "container": The DependencyContainer.
        - "mcp_registry": The MCPServerRegistry.

    Raises:
        ValueError: If required ports are not provided in production mode.
    """
    # 1. Dependency container
    container = create_dependency_container(redis_client=redis_client)

    # 2. MCP registry
    mcp_registry = create_mcp_registry()

    # 3. Resolve rate limiter
    rate_limiter = container.resolve(RateLimiterPort)  # type: ignore[type-abstract]

    # 4. Validate required ports
    if key_repository is None:
        raise ValueError(
            "key_repository is required. Provide an APIKeyRepositoryPort implementation."
        )
    if tenant_config_port is None:
        raise ValueError(
            "tenant_config_port is required. Provide a TenantConfigPort implementation."
        )

    # Register ports in container
    container.register_singleton(APIKeyRepositoryPort, key_repository)  # type: ignore[type-abstract]
    container.register_singleton(TenantConfigPort, tenant_config_port)  # type: ignore[type-abstract]

    # 5. Wire webhook dispatcher
    webhook_dispatcher = WebhookDispatcher(tenant_config_port=tenant_config_port)
    container.register_singleton(WebhookDispatchPort, webhook_dispatcher)  # type: ignore[type-abstract]

    # 6. Build Gateway application
    app = create_gateway_app(
        key_repository=key_repository,
        rate_limiter=rate_limiter,
        tenant_config_port=tenant_config_port,
        context_routes=context_routes,
    )

    # Attach container and registry to app state for runtime access
    app.state.container = container
    app.state.mcp_registry = mcp_registry

    logger.info("PRISM platform bootstrap complete")

    return {
        "app": app,
        "container": container,
        "mcp_registry": mcp_registry,
    }
