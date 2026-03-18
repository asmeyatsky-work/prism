"""
Catalogue MCP Server

Architectural Intent:
- MCP server for the Catalogue bounded context per skill2026 Principle 5
- Tools = write operations (ingest_product, update_product)
- Resources = read operations (get product by ID, list products)
- Prompts = reusable prompt templates (product_summary)
- This is the single MCP entry point for all catalogue operations

MCP Integration:
- Registered in the MCPServerRegistry during application bootstrap
- Communicates via stdio transport for local development, SSE for production
- Each tool/resource is tenant-scoped — tenant_id is required in all requests

Design Notes:
- Uses the MCP Python SDK (mcp) for server definition
- Delegates all business logic to application-layer use cases
- Serialises domain DTOs to JSON for MCP transport
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    TextContent,
    Tool,
)

from prism.catalogue.application.commands.ingest_product import (
    IngestProductCommand,
    IngestProductUseCase,
)
from prism.catalogue.application.commands.update_product import (
    UpdateProductCommand,
    UpdateProductUseCase,
)
from prism.catalogue.application.dtos.product_dto import ProductDTO
from prism.catalogue.application.queries.get_product import (
    GetProductQuery,
    GetProductQueryHandler,
)
from prism.catalogue.application.queries.list_products import (
    ListProductsQuery,
    ListProductsQueryHandler,
)
from prism.catalogue.domain.ports.repository_ports import ProductRepositoryPort
from prism.shared.application.dtos import PaginationParams
from prism.shared.domain.events import EventBusPort

# ── Server definition ────────────────────────────────────────────────

server = Server("prism-catalogue")


class CatalogueServerDependencies:
    """
    Dependency container for the Catalogue MCP server.

    Holds references to the use cases and query handlers that the MCP
    tools and resources delegate to. Must be initialised before the
    server starts handling requests.
    """

    ingest_use_case: IngestProductUseCase | None = None
    update_use_case: UpdateProductUseCase | None = None
    get_product_handler: GetProductQueryHandler | None = None
    list_products_handler: ListProductsQueryHandler | None = None


_deps = CatalogueServerDependencies()


def configure_server(
    product_repository: ProductRepositoryPort,
    event_bus: EventBusPort,
) -> None:
    """
    Configure the MCP server with its dependencies.

    Must be called before running the server. Wires up use cases
    and query handlers with the provided infrastructure ports.

    Args:
        product_repository: Implementation of ProductRepositoryPort.
        event_bus: Implementation of EventBusPort.
    """
    _deps.ingest_use_case = IngestProductUseCase(
        product_repository=product_repository,
        event_bus=event_bus,
    )
    _deps.update_use_case = UpdateProductUseCase(
        product_repository=product_repository,
        event_bus=event_bus,
    )
    _deps.get_product_handler = GetProductQueryHandler(
        product_repository=product_repository,
    )
    _deps.list_products_handler = ListProductsQueryHandler(
        product_repository=product_repository,
    )


# ── Tools (write operations) ────────────────────────────────────────


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available catalogue tools."""
    return [
        Tool(
            name="ingest_product",
            description=(
                "Ingest a new product into the PRISM catalogue. "
                "Creates the product aggregate, computes initial quality score, "
                "and publishes a ProductIngestedEvent."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tenant_id": {"type": "string", "description": "Tenant identifier"},
                    "sku": {"type": "string", "description": "Stock Keeping Unit"},
                    "name": {"type": "string", "description": "Product display name"},
                    "brand": {"type": "string", "description": "Brand name"},
                    "description": {"type": "string", "description": "Product description"},
                    "category": {"type": "string", "description": "Product category"},
                    "subcategory": {"type": "string", "description": "Product subcategory"},
                    "attributes": {
                        "type": "object",
                        "description": "Product attributes as key-value pairs",
                    },
                    "image_uris": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "GCS image URIs",
                    },
                    "price_amount": {"type": "number", "description": "Price amount"},
                    "price_currency": {"type": "string", "description": "ISO 4217 currency code"},
                    "taxonomy_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Taxonomy classification codes",
                    },
                    "source": {"type": "string", "description": "Ingestion source"},
                },
                "required": ["tenant_id", "sku", "name", "brand"],
            },
        ),
        Tool(
            name="update_product",
            description=(
                "Update an existing product in the catalogue. "
                "Supports partial updates — only provided fields are changed."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "tenant_id": {"type": "string", "description": "Tenant identifier"},
                    "product_id": {"type": "string", "description": "Product domain ID"},
                    "name": {"type": "string", "description": "Updated product name"},
                    "description": {"type": "string", "description": "Updated description"},
                    "category": {"type": "string", "description": "Updated category"},
                    "subcategory": {"type": "string", "description": "Updated subcategory"},
                    "attributes": {
                        "type": "object",
                        "description": "Attributes to merge",
                    },
                    "price_amount": {"type": "number", "description": "Updated price amount"},
                    "price_currency": {"type": "string", "description": "Updated currency code"},
                    "taxonomy_codes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Updated taxonomy codes",
                    },
                },
                "required": ["tenant_id", "product_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to the appropriate use case."""
    if name == "ingest_product":
        return await _handle_ingest_product(arguments)
    elif name == "update_product":
        return await _handle_update_product(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_ingest_product(args: dict[str, Any]) -> list[TextContent]:
    """Handle the ingest_product tool call."""
    if _deps.ingest_use_case is None:
        return [TextContent(type="text", text="Server not configured")]

    command = IngestProductCommand(**args)
    result = await _deps.ingest_use_case.execute(command)

    if result.success and result.value:
        return [
            TextContent(
                type="text",
                text=json.dumps(result.value.model_dump(), default=str),
            )
        ]
    return [TextContent(type="text", text=f"Error: {result.error}")]


async def _handle_update_product(args: dict[str, Any]) -> list[TextContent]:
    """Handle the update_product tool call."""
    if _deps.update_use_case is None:
        return [TextContent(type="text", text="Server not configured")]

    command = UpdateProductCommand(**args)
    result = await _deps.update_use_case.execute(command)

    if result.success and result.value:
        return [
            TextContent(
                type="text",
                text=json.dumps(result.value.model_dump(), default=str),
            )
        ]
    return [TextContent(type="text", text=f"Error: {result.error}")]


# ── Resources (read operations) ─────────────────────────────────────


@server.list_resources()
async def list_resources() -> list[Resource]:
    """List available catalogue resources."""
    return [
        Resource(
            uri="catalogue://products",
            name="Product List",
            description="Paginated list of products for a tenant",
            mimeType="application/json",
        ),
        Resource(
            uri="catalogue://products/{product_id}",
            name="Product Detail",
            description="Full product details by ID",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """
    Read a catalogue resource by URI.

    Supported URIs:
    - catalogue://products?tenant_id=X&offset=0&limit=50
    - catalogue://products/{product_id}?tenant_id=X
    """
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(uri)
    path = parsed.path.strip("/") if parsed.path else parsed.netloc
    params = parse_qs(parsed.query) if parsed.query else {}

    # Extract tenant_id from query params
    tenant_id = params.get("tenant_id", [""])[0]
    if not tenant_id:
        return json.dumps({"error": "tenant_id query parameter is required"})

    # Route: catalogue://products/{product_id}
    if "/" in path:
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "products":
            product_id = parts[1]
            return await _read_product(tenant_id, product_id)

    # Route: catalogue://products
    if path == "products" or path == "":
        offset = int(params.get("offset", ["0"])[0])
        limit = int(params.get("limit", ["50"])[0])
        return await _read_product_list(tenant_id, offset, limit)

    return json.dumps({"error": f"Unknown resource URI: {uri}"})


async def _read_product(tenant_id: str, product_id: str) -> str:
    """Read a single product resource."""
    if _deps.get_product_handler is None:
        return json.dumps({"error": "Server not configured"})

    query = GetProductQuery(tenant_id=tenant_id, product_id=product_id)
    result = await _deps.get_product_handler.execute(query)

    if result.success and result.data:
        return json.dumps(result.data.model_dump(), default=str)
    if result.success:
        return json.dumps({"error": "Product not found"})
    return json.dumps({"error": result.error})


async def _read_product_list(tenant_id: str, offset: int, limit: int) -> str:
    """Read a paginated product list resource."""
    if _deps.list_products_handler is None:
        return json.dumps({"error": "Server not configured"})

    query = ListProductsQuery(
        tenant_id=tenant_id,
        pagination=PaginationParams(offset=offset, limit=limit),
    )
    result = await _deps.list_products_handler.execute(query)

    if result.success and result.data is not None:
        return json.dumps(
            {
                "products": [p.model_dump() for p in result.data],
                "total_count": result.total_count,
                "offset": offset,
                "limit": limit,
            },
            default=str,
        )
    return json.dumps({"error": result.error or "No data"})


# ── Prompts ──────────────────────────────────────────────────────────


@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    """List available catalogue prompts."""
    return [
        Prompt(
            name="product_summary",
            description=(
                "Generate a concise product summary suitable for catalogue cards, "
                "search results, and AI-assisted merchandising."
            ),
            arguments=[
                PromptArgument(
                    name="product_id",
                    description="The product's domain ID",
                    required=True,
                ),
                PromptArgument(
                    name="tenant_id",
                    description="The tenant identifier",
                    required=True,
                ),
            ],
        ),
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    """Generate a catalogue prompt."""
    if name == "product_summary":
        return await _product_summary_prompt(arguments or {})
    raise ValueError(f"Unknown prompt: {name}")


async def _product_summary_prompt(args: dict[str, str]) -> GetPromptResult:
    """Generate the product_summary prompt with product context."""
    product_id = args.get("product_id", "")
    tenant_id = args.get("tenant_id", "")

    product_context = "No product data available."

    if _deps.get_product_handler and product_id and tenant_id:
        query = GetProductQuery(tenant_id=tenant_id, product_id=product_id)
        result = await _deps.get_product_handler.execute(query)
        if result.success and result.data:
            product_context = json.dumps(result.data.model_dump(), default=str, indent=2)

    return GetPromptResult(
        description="Generate a luxury product summary",
        messages=[
            PromptMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=(
                        "You are a luxury retail copywriter. Generate a concise, "
                        "sophisticated product summary suitable for a catalogue card.\n\n"
                        f"Product data:\n{product_context}\n\n"
                        "Requirements:\n"
                        "- 2-3 sentences maximum\n"
                        "- Highlight key materials and craftsmanship\n"
                        "- Use the brand's tone (sophisticated, understated luxury)\n"
                        "- Include the primary occasion or styling suggestion"
                    ),
                ),
            )
        ],
    )


# ── Entry point ──────────────────────────────────────────────────────


async def run_server() -> None:
    """
    Run the Catalogue MCP server using stdio transport.

    For production use, configure_server() must be called first to inject
    infrastructure dependencies.
    """
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_server())
