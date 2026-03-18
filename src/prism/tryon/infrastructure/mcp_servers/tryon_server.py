"""
Try-On MCP Server — Model Context Protocol endpoint

Architectural Intent:
- MCP server for the Try-On bounded context (per skill2026 Principle 5)
- Tools = write operations: process_tryon, compose_outfit
- Resources = read operations: tryon://result/{session_id}
- Each tool validates consent before processing customer images
- Customer image bytes are base64-decoded from the MCP request and processed in-memory

Transport: stdio (default) or SSE for remote deployment
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, TextContent, Tool

from prism.shared.domain.value_objects import ImageRef

from prism.tryon.application.commands.compose_outfit import ComposeOutfitUseCase
from prism.tryon.application.commands.process_tryon import ProcessTryOnUseCase
from prism.tryon.application.dtos.tryon_dto import TryOnRequestDTO
from prism.tryon.application.queries.get_tryon_result import (
    GetTryOnResultQuery,
    TryOnSessionRepository,
)
from prism.tryon.domain.ports.tryon_ports import (
    BodyExtractionPort,
    CompositionPort,
    StyleMatchingPort,
)

logger = logging.getLogger(__name__)

# --- MCP Server Definition ---

server = Server("prism-tryon")


def _body_extractor() -> BodyExtractionPort:
    """Resolve the body extractor from the DI container."""
    return server._body_extractor  # type: ignore[attr-defined]


def _compositor() -> CompositionPort:
    """Resolve the compositor from the DI container."""
    return server._compositor  # type: ignore[attr-defined]


def _style_matcher() -> StyleMatchingPort:
    """Resolve the style matcher from the DI container."""
    return server._style_matcher  # type: ignore[attr-defined]


def _session_repository() -> TryOnSessionRepository:
    """Resolve the session repository from the DI container."""
    return server._session_repository  # type: ignore[attr-defined]


# --- Tool Definitions ---

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Register available try-on tools."""
    return [
        Tool(
            name="process_tryon",
            description=(
                "Process a virtual try-on request. Takes a customer image (base64), "
                "product ID, and tenant context. Returns a composited try-on image URL. "
                "Requires explicit customer consent. Customer images are processed "
                "in-memory only and never persisted."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_image_base64": {
                        "type": "string",
                        "description": "Base64-encoded customer image (JPEG/PNG)",
                    },
                    "product_id": {
                        "type": "string",
                        "description": "Product ID to try on",
                    },
                    "tenant_id": {
                        "type": "string",
                        "description": "Tenant/brand identifier",
                    },
                    "consent": {
                        "type": "boolean",
                        "description": "Customer consent for image processing",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["APPAREL", "ACCESSORIES", "EYEWEAR", "JEWELLERY"],
                        "default": "APPAREL",
                    },
                    "product_image_bucket": {
                        "type": "string",
                        "description": "GCS bucket containing the product image",
                    },
                    "product_image_path": {
                        "type": "string",
                        "description": "Path to the product image in GCS",
                    },
                    "background_preset": {
                        "type": "string",
                        "default": "studio_white",
                    },
                    "lighting_preset": {
                        "type": "string",
                        "default": "soft_diffused",
                    },
                },
                "required": [
                    "customer_image_base64",
                    "product_id",
                    "tenant_id",
                    "consent",
                    "product_image_bucket",
                    "product_image_path",
                ],
            },
        ),
        Tool(
            name="compose_outfit",
            description=(
                "Generate a 'Complete the Look' outfit suggestion based on "
                "a product being tried on. Returns complementary product IDs "
                "with a style coherence score."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Try-on session ID",
                    },
                    "product_id": {
                        "type": "string",
                        "description": "Seed product ID for outfit generation",
                    },
                    "tenant_id": {
                        "type": "string",
                        "description": "Tenant/brand identifier",
                    },
                    "catalogue_context": {
                        "type": "object",
                        "description": "Additional catalogue metadata for styling",
                        "default": {},
                    },
                },
                "required": ["session_id", "product_id", "tenant_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to the appropriate use case."""
    if name == "process_tryon":
        return await _handle_process_tryon(arguments)
    elif name == "compose_outfit":
        return await _handle_compose_outfit(arguments)
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_process_tryon(args: dict[str, Any]) -> list[TextContent]:
    """Handle the process_tryon tool invocation."""
    # Decode customer image from base64 (in-memory only)
    try:
        customer_image_bytes = base64.b64decode(args["customer_image_base64"])
    except Exception as exc:
        return [TextContent(
            type="text",
            text=json.dumps({"error": f"Invalid base64 image: {exc}"}),
        )]

    # Build the request DTO
    request = TryOnRequestDTO(
        customer_image=customer_image_bytes,
        product_id=args["product_id"],
        tenant_id=args["tenant_id"],
        consent=args.get("consent", False),
        category=args.get("category", "APPAREL"),
        background_preset=args.get("background_preset", "studio_white"),
        lighting_preset=args.get("lighting_preset", "soft_diffused"),
    )

    product_image = ImageRef(
        bucket=args["product_image_bucket"],
        path=args["product_image_path"],
    )

    # Execute the use case
    use_case = ProcessTryOnUseCase(
        body_extractor=_body_extractor(),
        compositor=_compositor(),
    )
    result = await use_case.execute(request=request, product_image=product_image)

    if result.success and result.value is not None:
        return [TextContent(
            type="text",
            text=result.value.model_dump_json(indent=2),
        )]
    else:
        return [TextContent(
            type="text",
            text=json.dumps({"error": result.error, "code": result.error_code}),
        )]


async def _handle_compose_outfit(args: dict[str, Any]) -> list[TextContent]:
    """Handle the compose_outfit tool invocation."""
    use_case = ComposeOutfitUseCase(style_matcher=_style_matcher())

    result = await use_case.execute(
        session_id=args["session_id"],
        product_id=args["product_id"],
        tenant_id=args["tenant_id"],
        catalogue_context=args.get("catalogue_context"),
    )

    if result.success and result.value is not None:
        return [TextContent(
            type="text",
            text=result.value.model_dump_json(indent=2),
        )]
    else:
        return [TextContent(
            type="text",
            text=json.dumps({"error": result.error, "code": result.error_code}),
        )]


# --- Resource Definitions ---

@server.list_resources()
async def list_resources() -> list[Resource]:
    """Register available try-on resources."""
    return [
        Resource(
            uri="tryon://result/{session_id}",
            name="Try-On Result",
            description="Retrieve a completed virtual try-on result by session ID",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    """Read a try-on resource by URI."""
    # Parse the URI: tryon://result/{session_id}
    if uri.startswith("tryon://result/"):
        session_id = uri.removeprefix("tryon://result/")
        return await _handle_get_result(session_id)

    return json.dumps({"error": f"Unknown resource URI: {uri}"})


async def _handle_get_result(session_id: str) -> str:
    """Handle the tryon://result/{session_id} resource read."""
    query = GetTryOnResultQuery(repository=_session_repository())

    # For resource reads we need tenant context — extract from session
    # In production this would come from the MCP client context
    result = await query.execute(
        session_id=session_id,
        tenant_id="",  # Resolved from session in production
    )

    if result.success and result.data is not None:
        return result.data.model_dump_json(indent=2)
    else:
        return json.dumps({"error": result.error})


# --- Server Bootstrap ---

def configure(
    body_extractor: BodyExtractionPort,
    compositor: CompositionPort,
    style_matcher: StyleMatchingPort,
    session_repository: TryOnSessionRepository,
) -> Server:
    """
    Configure the MCP server with infrastructure dependencies.

    Called during application bootstrap to inject adapters into the server.

    Args:
        body_extractor: Implementation of BodyExtractionPort.
        compositor: Implementation of CompositionPort.
        style_matcher: Implementation of StyleMatchingPort.
        session_repository: Implementation of TryOnSessionRepository.

    Returns:
        The configured MCP Server instance.
    """
    server._body_extractor = body_extractor  # type: ignore[attr-defined]
    server._compositor = compositor  # type: ignore[attr-defined]
    server._style_matcher = style_matcher  # type: ignore[attr-defined]
    server._session_repository = session_repository  # type: ignore[attr-defined]
    return server


async def main() -> None:
    """Run the MCP server with stdio transport."""
    logger.info("Starting PRISM Try-On MCP server")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
