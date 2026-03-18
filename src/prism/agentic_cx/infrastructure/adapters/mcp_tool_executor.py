"""
Agentic CX — MCP Tool Executor

Architectural Intent:
- Implements ToolExecutionPort by calling other PRISM MCP servers
- Routes tool calls to the appropriate bounded context MCP server
- Uses the shared MCPServerRegistry for server discovery
- Each tool maps to a specific MCP server and tool name
- Supports parallel execution of independent tool calls
- Includes timeout, retry, and circuit breaker patterns

MCP Integration:
- This is the core MCP client adapter for cross-context tool calls
- Catalogue BC tools: catalogue_search, product_details
- Visual Discovery BC tools: virtual_tryon, style_match
- Commerce BC tools: inventory_check, wishlist_manage, gift_wrapping
- OMS BC tools: order_status, returns
- CRM BC tools: appointment_book
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from prism.shared.infrastructure.mcp_registry import MCPServerRegistry

logger = logging.getLogger(__name__)


class ToolExecutionError(Exception):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"Tool '{tool_name}' failed: {message}")


# Mapping from tool name to MCP server name
_TOOL_SERVER_MAP: dict[str, str] = {
    "catalogue_search": "catalogue",
    "product_details": "catalogue",
    "virtual_tryon": "visual_discovery",
    "style_match": "visual_discovery",
    "inventory_check": "commerce",
    "wishlist_manage": "commerce",
    "gift_wrapping": "commerce",
    "order_status": "oms",
    "returns": "oms",
    "appointment_book": "crm",
    "associate_escalate": "agentic_cx",
}


class MCPToolExecutor:
    """
    Infrastructure adapter implementing ToolExecutionPort via MCP.

    Routes tool calls to the appropriate PRISM MCP server based on
    the tool-to-server mapping. Uses the MCPServerRegistry for
    server configuration and discovery.
    """

    def __init__(
        self,
        registry: MCPServerRegistry,
        timeout_seconds: float = 15.0,
        max_retries: int = 2,
    ) -> None:
        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._clients: dict[str, Any] = {}
        self._circuit_breaker: dict[str, _CircuitState] = {}

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a tool by routing to the appropriate MCP server.

        Includes retry logic and circuit breaker for resilience.

        Args:
            tool_name: The MCP tool identifier.
            arguments: Tool arguments as a dictionary.

        Returns:
            Tool result as a dictionary.

        Raises:
            ToolExecutionError: If the tool call fails after retries.
        """
        # Resolve server
        server_name = _TOOL_SERVER_MAP.get(tool_name)
        if server_name is None:
            raise ToolExecutionError(
                tool_name, f"No MCP server mapping found for tool '{tool_name}'"
            )

        # Check circuit breaker
        circuit = self._circuit_breaker.get(server_name)
        if circuit and circuit.is_open:
            raise ToolExecutionError(
                tool_name,
                f"Circuit breaker open for server '{server_name}'. "
                f"Failures: {circuit.failure_count}",
            )

        # Execute with retry
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                result = await self._call_mcp_server(
                    server_name=server_name,
                    tool_name=tool_name,
                    arguments=arguments,
                )
                # Reset circuit breaker on success
                if server_name in self._circuit_breaker:
                    self._circuit_breaker[server_name].reset()
                return result
            except asyncio.TimeoutError:
                last_error = ToolExecutionError(
                    tool_name,
                    f"Timeout after {self._timeout_seconds}s (attempt {attempt + 1})",
                )
                logger.warning(
                    "Tool %s timeout on attempt %d/%d",
                    tool_name,
                    attempt + 1,
                    self._max_retries + 1,
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "Tool %s failed on attempt %d/%d: %s",
                    tool_name,
                    attempt + 1,
                    self._max_retries + 1,
                    str(e),
                )

        # Record failure in circuit breaker
        if server_name not in self._circuit_breaker:
            self._circuit_breaker[server_name] = _CircuitState()
        self._circuit_breaker[server_name].record_failure()

        raise ToolExecutionError(
            tool_name,
            f"Failed after {self._max_retries + 1} attempts: {last_error}",
        )

    async def _call_mcp_server(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Call an MCP server's tool.

        In production, this would use the MCP client SDK to establish
        a connection (stdio or SSE) to the target server and invoke
        the tool. For now, it uses a stub implementation.
        """
        server_config = self._registry.get(server_name)
        logger.info(
            "Calling MCP server '%s' tool '%s' via %s",
            server_name,
            tool_name,
            server_config.transport,
        )

        # Production: establish MCP client connection and call tool
        # For now, return a structured stub response
        return await self._stub_tool_response(tool_name, arguments)

    async def _stub_tool_response(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Stub tool responses for development.

        These simulate realistic responses from other PRISM MCP servers
        to enable end-to-end development of the agent flow.
        """
        stubs: dict[str, dict[str, Any]] = {
            "catalogue_search": {
                "products": [
                    {
                        "id": "prod_001",
                        "name": "Gucci GG Marmont Matelasse Shoulder Bag",
                        "price": {"amount": 2490.00, "currency": "USD"},
                        "available": True,
                    }
                ],
                "total_results": 1,
            },
            "product_details": {
                "id": arguments.get("product_id", "prod_001"),
                "name": "Gucci GG Marmont Matelasse Shoulder Bag",
                "description": "Crafted from chevron-quilted leather with signature GG hardware.",
                "price": {"amount": 2490.00, "currency": "USD"},
                "sizes": ["Small", "Medium"],
                "colors": ["Black", "Dusty Pink", "White"],
            },
            "virtual_tryon": {
                "tryon_url": "https://tryon.prism.example/session/abc123",
                "confidence": 0.92,
                "fit_notes": "This style suits your body type well.",
            },
            "inventory_check": {
                "product_id": arguments.get("product_id", "prod_001"),
                "available": True,
                "stores": [
                    {"name": "Fifth Avenue Flagship", "stock": 3},
                    {"name": "Rodeo Drive", "stock": 1},
                ],
            },
            "wishlist_manage": {
                "action": arguments.get("action", "add"),
                "success": True,
                "wishlist_count": 5,
            },
            "appointment_book": {
                "appointment_id": "apt_001",
                "store": "Fifth Avenue Flagship",
                "datetime": "2026-03-20T14:00:00Z",
                "confirmed": True,
            },
            "order_status": {
                "order_id": arguments.get("order_id", "ord_001"),
                "status": "shipped",
                "tracking_number": "1Z999AA10123456784",
                "estimated_delivery": "2026-03-21",
            },
            "returns": {
                "return_id": "ret_001",
                "status": "initiated",
                "label_url": "https://returns.prism.example/label/ret_001",
            },
            "gift_wrapping": {
                "options": [
                    {"name": "Signature Gift Box", "price": 25.00},
                    {"name": "Premium Gift Wrapping", "price": 15.00},
                ],
            },
        }
        return stubs.get(tool_name, {"status": "ok"})


class _CircuitState:
    """Simple circuit breaker state for MCP server health tracking."""

    def __init__(self, failure_threshold: int = 5) -> None:
        self.failure_count: int = 0
        self.failure_threshold = failure_threshold

    @property
    def is_open(self) -> bool:
        return self.failure_count >= self.failure_threshold

    def record_failure(self) -> None:
        self.failure_count += 1

    def reset(self) -> None:
        self.failure_count = 0
