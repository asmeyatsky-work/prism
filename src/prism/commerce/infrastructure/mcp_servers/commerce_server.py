"""
Commerce MCP Server — Model Context Protocol Server for Commerce Bounded Context

Architectural Intent:
- Exposes commerce operations as MCP tools and resources
- Tools = write operations: process_ucp_event, sync_google_shopping, push_enriched_product
- Resources = read operations: commerce://inventory/{product_id}, commerce://feed/{tenant_id}
- Per skill2026 Principle 5: MCP-Native Integration Architecture
- Per skill2026 Rule 2: MCP tool schemas mirror port method signatures
- Registers with the shared MCPServerRegistry for platform-wide discovery

Tool Catalogue:
  process_ucp_event       — Receive and process a UCP event
  sync_google_shopping    — Publish enriched products to Google Shopping
  push_enriched_product   — Push enriched data back to UCP

Resource Catalogue:
  commerce://inventory/{product_id}  — Get inventory availability
  commerce://feed/{tenant_id}        — Get feed sync status
"""

from __future__ import annotations

import json
import logging
from typing import Any

from prism.commerce.application.commands.process_ucp_event import ProcessUCPEventUseCase
from prism.commerce.application.commands.push_enriched_product import (
    PushEnrichedProductUseCase,
)
from prism.commerce.application.commands.sync_google_shopping import (
    SyncGoogleShoppingUseCase,
)
from prism.commerce.application.queries.get_feed_status import (
    GetGoogleShoppingFeedStatusQuery,
)
from prism.commerce.application.queries.get_inventory import GetInventoryQuery
from prism.shared.infrastructure.mcp_registry import MCPServerConfig

logger = logging.getLogger(__name__)

# MCP server configuration for registry
COMMERCE_MCP_CONFIG = MCPServerConfig(
    name="commerce",
    module="prism.commerce.infrastructure.mcp_servers.commerce_server",
    description="Commerce bounded context — UCP connector, inventory, and Google Shopping feeds",
    transport="stdio",
    tools=(
        "process_ucp_event",
        "sync_google_shopping",
        "push_enriched_product",
    ),
    resources=(
        "commerce://inventory/{product_id}",
        "commerce://feed/{tenant_id}",
    ),
)


class CommerceMCPServer:
    """
    MCP server for the Commerce bounded context.

    Exposes commerce use cases as MCP tools (write operations) and
    domain queries as MCP resources (read operations). Designed to be
    consumed by AI agents and cross-context MCP clients.
    """

    def __init__(
        self,
        process_ucp_event_use_case: ProcessUCPEventUseCase,
        sync_google_shopping_use_case: SyncGoogleShoppingUseCase,
        push_enriched_product_use_case: PushEnrichedProductUseCase,
        get_inventory_query: GetInventoryQuery,
        get_feed_status_query: GetGoogleShoppingFeedStatusQuery,
    ) -> None:
        self._process_ucp_event = process_ucp_event_use_case
        self._sync_google_shopping = sync_google_shopping_use_case
        self._push_enriched_product = push_enriched_product_use_case
        self._get_inventory = get_inventory_query
        self._get_feed_status = get_feed_status_query

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """
        Return MCP tool definitions for this server.

        Each tool definition includes name, description, and input schema
        matching the corresponding port method signature.
        """
        return [
            {
                "name": "process_ucp_event",
                "description": (
                    "Receive and process a raw UCP event. Classifies the event, "
                    "persists it, and triggers downstream processing including "
                    "inventory updates and AI enrichment."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "event_data": {
                            "type": "object",
                            "description": "Raw UCP event data with event_type, source, and payload",
                            "properties": {
                                "event_id": {"type": "string"},
                                "event_type": {"type": "string"},
                                "source": {"type": "string"},
                                "payload": {"type": "object"},
                                "tenant_id": {"type": "string"},
                            },
                            "required": ["event_type", "payload"],
                        },
                    },
                    "required": ["event_data"],
                },
            },
            {
                "name": "sync_google_shopping",
                "description": (
                    "Publish enriched product data to Google Merchant Center. "
                    "Accepts a list of PCES-format products and tenant identifier."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "products": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "List of PCES-format product dictionaries",
                        },
                        "tenant_id": {
                            "type": "string",
                            "description": "Tenant (brand) identifier",
                        },
                    },
                    "required": ["products", "tenant_id"],
                },
            },
            {
                "name": "push_enriched_product",
                "description": (
                    "Push PRISM-enriched product data back to the UCP. "
                    "Requires product_data with at least an 'id' or 'sku' field."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product_data": {
                            "type": "object",
                            "description": "PCES-format enriched product data",
                            "properties": {
                                "id": {"type": "string"},
                                "sku": {"type": "string"},
                                "tenant_id": {"type": "string"},
                            },
                        },
                    },
                    "required": ["product_data"],
                },
            },
        ]

    def get_resource_definitions(self) -> list[dict[str, Any]]:
        """
        Return MCP resource definitions for this server.

        Resources are read-only data endpoints for inventory and feed status.
        """
        return [
            {
                "uri": "commerce://inventory/{product_id}",
                "name": "Product Inventory",
                "description": "Get real-time inventory availability for a product",
                "mimeType": "application/json",
                "parameters": {
                    "product_id": {"type": "string", "required": True},
                    "tenant_id": {"type": "string", "required": True},
                },
            },
            {
                "uri": "commerce://feed/{tenant_id}",
                "name": "Google Shopping Feed Status",
                "description": "Get synchronisation status of a tenant's Google Shopping feed",
                "mimeType": "application/json",
                "parameters": {
                    "feed_id": {"type": "string", "required": True},
                },
            },
        ]

    async def handle_tool_call(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Dispatch an MCP tool call to the appropriate use case.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments from the MCP client.

        Returns:
            Tool result as a dictionary.
        """
        logger.info("MCP tool call: tool=%s", tool_name)

        if tool_name == "process_ucp_event":
            event_data = arguments.get("event_data", {})
            result = await self._process_ucp_event.execute(event_data)
            return {
                "success": result.success,
                "error": result.error,
                "event_id": result.value.id if result.success and result.value else None,
            }

        elif tool_name == "sync_google_shopping":
            products = arguments.get("products", [])
            tenant_id = arguments.get("tenant_id", "")
            result = await self._sync_google_shopping.execute(products, tenant_id)
            return {
                "success": result.success,
                "error": result.error,
                "feed_id": result.value.feed_id if result.success and result.value else None,
                "product_count": len(products),
            }

        elif tool_name == "push_enriched_product":
            product_data = arguments.get("product_data", {})
            result = await self._push_enriched_product.execute(product_data)
            return {
                "success": result.success,
                "error": result.error,
            }

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def handle_resource_read(
        self, uri: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Dispatch an MCP resource read to the appropriate query.

        Args:
            uri: Resource URI pattern.
            parameters: Query parameters from the MCP client.

        Returns:
            Resource data as a dictionary.
        """
        logger.info("MCP resource read: uri=%s", uri)

        if uri.startswith("commerce://inventory/"):
            product_id = parameters.get("product_id", "")
            tenant_id = parameters.get("tenant_id", "")
            result = await self._get_inventory.execute(product_id, tenant_id)
            if result.success and result.data:
                return result.data.model_dump()
            return {"error": result.error or "Not found"}

        elif uri.startswith("commerce://feed/"):
            feed_id = parameters.get("feed_id", "")
            result = await self._get_feed_status.execute(feed_id)
            if result.success and result.data:
                return result.data.model_dump()
            return {"error": result.error or "Not found"}

        else:
            return {"error": f"Unknown resource: {uri}"}
