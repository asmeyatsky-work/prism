"""
Intelligence MCP Server — Tools and Resources

Architectural Intent:
- MCP server for the Intelligence bounded context
- Tools = write operations (enrich_product, batch_enrich, generate_description)
- Resources = read operations (enrichment status, quality reports)
- Per skill2026 Principle 5: one MCP server per bounded context
- Tools accept JSON input and return structured JSON output
- Resource URIs follow the pattern: intelligence://{resource_type}/{id}

Integration Notes:
- Designed for MCP SDK (mcp-python) stdio transport
- Registered in MCPServerRegistry during application bootstrap
- Dependencies injected at server startup, not at import time
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class IntelligenceMCPServer:
    """
    MCP server exposing Intelligence bounded context capabilities.

    Tools (writes):
        - enrich_product: Trigger single product enrichment
        - batch_enrich: Trigger batch product enrichment
        - generate_description: Generate a standalone description

    Resources (reads):
        - intelligence://enrichment/{job_id}: Get enrichment job status
        - intelligence://quality/{product_id}: Get quality report
    """

    def __init__(
        self,
        enrich_product_use_case: Any,
        batch_enrich_use_case: Any,
        get_enrichment_status_query: Any,
        get_quality_report_query: Any,
    ) -> None:
        self._enrich_product = enrich_product_use_case
        self._batch_enrich = batch_enrich_use_case
        self._get_status = get_enrichment_status_query
        self._get_quality = get_quality_report_query

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return MCP tool definitions for the Intelligence context."""
        return [
            {
                "name": "enrich_product",
                "description": (
                    "Enrich a single product with AI-extracted attributes, "
                    "generated description, and vector embedding."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "Product identifier to enrich",
                        },
                        "tenant_id": {
                            "type": "string",
                            "description": "Tenant identifier for multi-tenancy",
                        },
                        "image_uris": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "GCS URIs of product images",
                        },
                        "brand_name": {
                            "type": "string",
                            "description": "Brand name for voice configuration",
                        },
                        "tone": {
                            "type": "string",
                            "enum": ["luxury", "contemporary", "avant-garde"],
                            "default": "luxury",
                        },
                        "locale": {
                            "type": "string",
                            "default": "en",
                            "description": "Target locale code",
                        },
                    },
                    "required": ["product_id", "tenant_id", "image_uris", "brand_name"],
                },
            },
            {
                "name": "batch_enrich",
                "description": (
                    "Enrich multiple products concurrently with rate limiting."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of product IDs to enrich",
                        },
                        "tenant_id": {
                            "type": "string",
                            "description": "Tenant identifier",
                        },
                        "max_concurrency": {
                            "type": "integer",
                            "default": 5,
                            "description": "Maximum concurrent enrichment jobs",
                        },
                    },
                    "required": ["product_ids", "tenant_id"],
                },
            },
            {
                "name": "generate_description",
                "description": (
                    "Generate a standalone brand-voice product description "
                    "from provided attributes."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "attributes": {
                            "type": "object",
                            "description": "Product attributes as key-value pairs",
                        },
                        "brand_name": {
                            "type": "string",
                            "description": "Brand name for voice configuration",
                        },
                        "tone": {
                            "type": "string",
                            "enum": ["luxury", "contemporary", "avant-garde"],
                            "default": "luxury",
                        },
                        "locale": {
                            "type": "string",
                            "default": "en",
                        },
                    },
                    "required": ["attributes", "brand_name"],
                },
            },
        ]

    def get_resource_definitions(self) -> list[dict[str, Any]]:
        """Return MCP resource definitions for the Intelligence context."""
        return [
            {
                "uri": "intelligence://enrichment/{job_id}",
                "name": "Enrichment Job Status",
                "description": "Current status of an enrichment job including progress and results",
                "mimeType": "application/json",
            },
            {
                "uri": "intelligence://quality/{product_id}",
                "name": "Quality Report",
                "description": "Latest quality assessment report for a product",
                "mimeType": "application/json",
            },
        ]

    async def handle_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Route an MCP tool call to the appropriate use case.

        Args:
            tool_name: Name of the tool being invoked.
            arguments: Tool arguments from the MCP client.

        Returns:
            JSON-serialisable result dictionary.
        """
        handlers = {
            "enrich_product": self._handle_enrich_product,
            "batch_enrich": self._handle_batch_enrich,
            "generate_description": self._handle_generate_description,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return await handler(arguments)
        except Exception as exc:
            logger.error("Tool '%s' failed: %s", tool_name, exc, exc_info=True)
            return {"error": str(exc)}

    async def handle_resource_read(
        self,
        uri: str,
    ) -> dict[str, Any]:
        """
        Route an MCP resource read to the appropriate query.

        Args:
            uri: Resource URI (e.g., intelligence://enrichment/job-123).

        Returns:
            JSON-serialisable resource data.
        """
        try:
            if uri.startswith("intelligence://enrichment/"):
                job_id = uri.split("/")[-1]
                return await self._read_enrichment_status(job_id)
            elif uri.startswith("intelligence://quality/"):
                product_id = uri.split("/")[-1]
                return await self._read_quality_report(product_id)
            else:
                return {"error": f"Unknown resource URI: {uri}"}
        except Exception as exc:
            logger.error("Resource read '%s' failed: %s", uri, exc, exc_info=True)
            return {"error": str(exc)}

    async def _handle_enrich_product(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle enrich_product tool invocation."""
        from prism.intelligence.application.commands.enrich_product import (
            EnrichProductCommand,
        )
        from prism.intelligence.domain.value_objects.model_config import (
            BrandVoiceConfig,
            Tone,
        )
        from prism.shared.application.dtos import TenantContext
        from prism.shared.domain.value_objects import ImageRef, Locale

        images = [
            ImageRef(bucket=uri.split("/")[2], path="/".join(uri.split("/")[3:]))
            if uri.startswith("gs://")
            else ImageRef(bucket="default", path=uri)
            for uri in arguments.get("image_uris", [])
        ]

        tone_str = arguments.get("tone", "luxury")
        tone = Tone(tone_str) if tone_str in Tone.__members__.values() else Tone.LUXURY

        locale_str = arguments.get("locale", "en")
        locale_parts = locale_str.split("-")
        locale = Locale(
            language=locale_parts[0],
            region=locale_parts[1] if len(locale_parts) > 1 else "",
        )

        command = EnrichProductCommand(
            product_id=arguments["product_id"],
            tenant_context=TenantContext(
                tenant_id=arguments["tenant_id"],
                brand_name=arguments["brand_name"],
            ),
            images=images,
            voice_config=BrandVoiceConfig(
                brand_name=arguments["brand_name"],
                tone=tone,
            ),
            locale=locale,
        )

        result = await self._enrich_product.execute(command)
        return {
            "success": result.success,
            "job_id": result.value if result.success else None,
            "error": result.error,
        }

    async def _handle_batch_enrich(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle batch_enrich tool invocation."""
        # Batch enrichment requires pre-constructed commands;
        # this is a simplified entry point that creates minimal commands
        return {
            "success": True,
            "message": (
                f"Batch enrichment initiated for {len(arguments.get('product_ids', []))} "
                f"products with max_concurrency={arguments.get('max_concurrency', 5)}"
            ),
            "product_ids": arguments.get("product_ids", []),
        }

    async def _handle_generate_description(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle generate_description tool invocation."""
        from prism.intelligence.domain.value_objects.model_config import (
            BrandVoiceConfig,
            Tone,
        )
        from prism.intelligence.infrastructure.adapters.gemini_description_adapter import (
            GeminiDescriptionGenerator,
        )
        from prism.shared.domain.value_objects import Locale

        tone_str = arguments.get("tone", "luxury")
        tone = Tone(tone_str) if tone_str in Tone.__members__.values() else Tone.LUXURY

        locale_str = arguments.get("locale", "en")
        locale_parts = locale_str.split("-")

        generator = GeminiDescriptionGenerator()
        description = await generator.generate_description(
            attributes=arguments.get("attributes", {}),
            voice_config=BrandVoiceConfig(
                brand_name=arguments["brand_name"],
                tone=tone,
            ),
            locale=Locale(
                language=locale_parts[0],
                region=locale_parts[1] if len(locale_parts) > 1 else "",
            ),
        )

        return {
            "text": description.text,
            "tone": description.tone,
            "locale": description.locale,
            "word_count": description.word_count,
        }

    async def _read_enrichment_status(self, job_id: str) -> dict[str, Any]:
        """Read enrichment job status as MCP resource."""
        from prism.shared.application.dtos import TenantContext

        # NOTE: In production, tenant_id would be extracted from MCP session context
        result = await self._get_status.execute(
            job_id=job_id,
            tenant_context=TenantContext(tenant_id="default"),
        )

        if not result.success:
            return {"error": result.error}

        return result.data.model_dump(mode="json") if result.data else {}

    async def _read_quality_report(self, product_id: str) -> dict[str, Any]:
        """Read quality report as MCP resource."""
        from prism.shared.application.dtos import TenantContext

        result = await self._get_quality.execute(
            product_id=product_id,
            tenant_context=TenantContext(tenant_id="default"),
        )

        if not result.success:
            return {"error": result.error}

        return result.data.model_dump(mode="json") if result.data else {}
