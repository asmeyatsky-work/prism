"""
Discovery MCP Server — Model Context Protocol server for the Discovery context.

Architectural Intent:
- MCP server per bounded context (skill2026 Principle 5)
- Tools = write operations (execute_search)
- Resources = read operations (facets, analytics)
- Prompts = AI-assisted refinement (search_suggestion)
- Follows the MCP Python SDK conventions for tool/resource registration

MCP Integration:
- Registered in the central MCPServerRegistry during application bootstrap
- Transport: stdio (for local dev) or SSE (for production deployment)
- All operations are tenant-scoped via the request context
"""

from __future__ import annotations

import json
import logging
from typing import Any

from prism.discovery.application.commands.execute_search import ExecuteSearchUseCase
from prism.discovery.application.dtos.search_dto import SearchRequestDTO
from prism.discovery.application.queries.get_facets import GetFacetsQuery
from prism.discovery.application.queries.get_search_analytics import (
    GetSearchAnalyticsQuery,
)

logger = logging.getLogger(__name__)


class DiscoveryMCPServer:
    """
    MCP server for the Discovery bounded context.

    Exposes search capabilities as MCP tools and resources. In production,
    this is served via the MCP Python SDK's Server class. This implementation
    provides the handler methods that are registered with the SDK.
    """

    SERVER_NAME = "prism-discovery"
    SERVER_VERSION = "1.0.0"

    def __init__(
        self,
        execute_search_use_case: ExecuteSearchUseCase,
        get_facets_query: GetFacetsQuery,
        get_analytics_query: GetSearchAnalyticsQuery,
    ) -> None:
        self._execute_search = execute_search_use_case
        self._get_facets = get_facets_query
        self._get_analytics = get_analytics_query

    # ──────────────────────────────────────────────
    # Tool definitions (write operations)
    # ──────────────────────────────────────────────

    def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP tool definitions for the Discovery context."""
        return [
            {
                "name": "execute_search",
                "description": (
                    "Execute a multimodal product search across the luxury "
                    "catalogue. Supports text, image, and hybrid (text+image) "
                    "modalities with optional personalisation re-ranking."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tenant_id": {
                            "type": "string",
                            "description": "Brand tenant identifier",
                        },
                        "query_text": {
                            "type": "string",
                            "description": "Text search query (required for TEXT/HYBRID)",
                        },
                        "image_uri": {
                            "type": "string",
                            "description": "GCS URI of reference image (required for IMAGE/HYBRID)",
                        },
                        "modality": {
                            "type": "string",
                            "enum": ["TEXT", "IMAGE", "HYBRID", "VOICE"],
                            "description": "Search input modality",
                            "default": "TEXT",
                        },
                        "filters": {
                            "type": "object",
                            "description": "Facet filters to apply",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 20,
                        },
                        "customer_id": {
                            "type": "string",
                            "description": "Customer ID for personalised results",
                        },
                        "session_id": {
                            "type": "string",
                            "description": "Existing session ID to continue",
                        },
                    },
                    "required": ["tenant_id"],
                },
            }
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Handle an MCP tool invocation."""
        if name == "execute_search":
            return await self._handle_execute_search(arguments)

        return [{"type": "text", "text": f"Unknown tool: {name}"}]

    async def _handle_execute_search(
        self,
        arguments: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Handle the execute_search tool call."""
        request = SearchRequestDTO(**arguments)
        result = await self._execute_search.execute(request)

        if not result.success:
            return [{"type": "text", "text": f"Search failed: {result.error}"}]

        response = result.value
        return [
            {
                "type": "text",
                "text": json.dumps(response.model_dump(), default=str),
            }
        ]

    # ──────────────────────────────────────────────
    # Resource definitions (read operations)
    # ──────────────────────────────────────────────

    def list_resources(self) -> list[dict[str, Any]]:
        """Return MCP resource definitions for the Discovery context."""
        return [
            {
                "uri": "discovery://facets/{tenant_id}",
                "name": "Discovery Facets",
                "description": (
                    "Available search facets for a brand. Returns facet "
                    "dimensions (category, material, occasion, heritage, etc.) "
                    "with their values and counts."
                ),
                "mimeType": "application/json",
            },
            {
                "uri": "discovery://analytics/{session_id}",
                "name": "Search Session Analytics",
                "description": (
                    "Analytics for a search session including query count, "
                    "results served, clicks, and engagement rate."
                ),
                "mimeType": "application/json",
            },
        ]

    async def read_resource(
        self,
        uri: str,
    ) -> str:
        """Handle an MCP resource read."""
        if uri.startswith("discovery://facets/"):
            tenant_id = uri.split("/")[-1]
            return await self._handle_read_facets(tenant_id)

        if uri.startswith("discovery://analytics/"):
            session_id = uri.split("/")[-1]
            return await self._handle_read_analytics(session_id)

        return json.dumps({"error": f"Unknown resource: {uri}"})

    async def _handle_read_facets(self, tenant_id: str) -> str:
        """Handle reading facets for a tenant."""
        result = await self._get_facets.execute(tenant_id=tenant_id)

        if not result.success:
            return json.dumps({"error": result.error})

        facets = result.data or []
        return json.dumps(
            [f.model_dump() for f in facets],
            default=str,
        )

    async def _handle_read_analytics(self, session_id: str) -> str:
        """Handle reading analytics for a session."""
        # Note: tenant_id would normally come from auth context.
        # For MCP resource reads, we pass empty and let the query handle it.
        result = await self._get_analytics.execute(
            session_id=session_id,
            tenant_id="",
        )

        if not result.success:
            return json.dumps({"error": result.error})

        analytics = result.data
        return json.dumps(analytics.model_dump() if analytics else {}, default=str)

    # ──────────────────────────────────────────────
    # Prompt definitions (AI-assisted refinement)
    # ──────────────────────────────────────────────

    def list_prompts(self) -> list[dict[str, Any]]:
        """Return MCP prompt definitions for the Discovery context."""
        return [
            {
                "name": "search_suggestion",
                "description": (
                    "Suggests search refinements based on the current query "
                    "and results. Helps luxury retail advisors guide customers "
                    "towards relevant products."
                ),
                "arguments": [
                    {
                        "name": "query_text",
                        "description": "The current search query",
                        "required": True,
                    },
                    {
                        "name": "result_count",
                        "description": "Number of results returned",
                        "required": False,
                    },
                    {
                        "name": "tenant_id",
                        "description": "Brand tenant identifier",
                        "required": True,
                    },
                ],
            }
        ]

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, str],
    ) -> dict[str, Any]:
        """Handle an MCP prompt request."""
        if name == "search_suggestion":
            return self._build_search_suggestion_prompt(arguments)

        return {
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": f"Unknown prompt: {name}"},
                }
            ]
        }

    def _build_search_suggestion_prompt(
        self,
        arguments: dict[str, str],
    ) -> dict[str, Any]:
        """Build the search_suggestion prompt messages."""
        query_text = arguments.get("query_text", "")
        result_count = arguments.get("result_count", "0")
        tenant_id = arguments.get("tenant_id", "")

        system_message = (
            "You are a luxury retail search advisor for PRISM. Your role is to "
            "suggest search refinements that help customers discover products "
            "they will love. Consider the brand's heritage, seasonal collections, "
            "and the customer's apparent intent."
        )

        user_message = (
            f"The customer searched for: '{query_text}'\n"
            f"The search returned {result_count} results for brand {tenant_id}.\n\n"
            "Suggest 3-5 search refinements that could help the customer "
            "find what they are looking for. Consider:\n"
            "- More specific material or colour filters\n"
            "- Related product categories\n"
            "- Seasonal or occasion-based suggestions\n"
            "- Heritage or collection-based refinements"
        )

        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": {"type": "text", "text": system_message},
                },
                {
                    "role": "user",
                    "content": {"type": "text", "text": user_message},
                },
            ]
        }
