"""
Payment Infrastructure — MCP Server

Architectural Intent:
- MCP server for the Payment bounded context
- Tools (write operations): process_payment, capture_payment, refund_payment, check_bnpl
- Resources (read operations): payment://status/{payment_id}, payment://fx/{source}/{target}
- Per skill2026 Principle 5: MCP-Native Integration Architecture
- Registered in the shared MCPServerRegistry for platform-wide discovery

MCP Integration:
- Each tool maps to a use case in the application layer
- Each resource maps to a query in the application layer
- Transport: stdio (default) or SSE for remote deployment
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from prism.shared.infrastructure.mcp_registry import MCPServerConfig, MCPServerRegistry

logger = logging.getLogger(__name__)


# -- Server Configuration ------------------------------------------------

PAYMENT_MCP_CONFIG = MCPServerConfig(
    name="payment",
    module="prism.payment.infrastructure.mcp_servers.payment_server",
    description="Payment orchestration — FlowRoute routing, authorisation, capture, refund, BNPL, and FX rates",
    transport="stdio",
    tools=(
        "process_payment",
        "capture_payment",
        "refund_payment",
        "check_bnpl",
    ),
    resources=(
        "payment://status/{payment_id}",
        "payment://fx/{source}/{target}",
    ),
)


def register_payment_server(registry: MCPServerRegistry) -> None:
    """Register the Payment MCP server in the platform registry."""
    registry.register(PAYMENT_MCP_CONFIG)


# -- Tool Definitions ----------------------------------------------------

@dataclass(frozen=True)
class MCPToolResult:
    """Standardised result from an MCP tool invocation."""

    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None

    def to_json(self) -> str:
        if self.success:
            return json.dumps({"success": True, "data": self.data})
        return json.dumps({"success": False, "error": self.error})


class PaymentMCPServer:
    """
    MCP server exposing payment tools and resources.

    In production, this class is instantiated by the MCP runtime and
    receives tool/resource requests via the configured transport.
    Use case instances are injected at construction time.
    """

    def __init__(
        self,
        process_payment_use_case: Any,
        capture_payment_use_case: Any,
        refund_payment_use_case: Any,
        bnpl_port: Any,
        get_payment_status_query: Any,
        get_fx_comparison_query: Any,
    ) -> None:
        self._process_payment = process_payment_use_case
        self._capture_payment = capture_payment_use_case
        self._refund_payment = refund_payment_use_case
        self._bnpl_port = bnpl_port
        self._get_payment_status = get_payment_status_query
        self._get_fx_comparison = get_fx_comparison_query

        self._tools = {
            "process_payment": self._handle_process_payment,
            "capture_payment": self._handle_capture_payment,
            "refund_payment": self._handle_refund_payment,
            "check_bnpl": self._handle_check_bnpl,
        }

        self._resources = {
            "payment://status": self._handle_get_payment_status,
            "payment://fx": self._handle_get_fx_comparison,
        }

    # -- Tool Handlers ---------------------------------------------------

    async def handle_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPToolResult:
        """Route an MCP tool invocation to the appropriate handler."""
        handler = self._tools.get(tool_name)
        if handler is None:
            return MCPToolResult(success=False, error=f"Unknown tool: {tool_name}")

        try:
            return await handler(arguments)
        except Exception as exc:
            logger.exception("Tool '%s' failed", tool_name)
            return MCPToolResult(success=False, error=str(exc))

    async def handle_resource(self, uri: str) -> MCPToolResult:
        """Route an MCP resource request to the appropriate handler."""
        if uri.startswith("payment://status/"):
            payment_id = uri.removeprefix("payment://status/")
            return await self._handle_get_payment_status({"payment_id": payment_id})

        if uri.startswith("payment://fx/"):
            parts = uri.removeprefix("payment://fx/").split("/")
            if len(parts) == 2:
                return await self._handle_get_fx_comparison({
                    "source_currency": parts[0],
                    "target_currency": parts[1],
                    "amount": 1000.0,  # Default comparison amount
                })

        return MCPToolResult(success=False, error=f"Unknown resource URI: {uri}")

    # -- Tool Implementations -------------------------------------------

    async def _handle_process_payment(self, args: dict[str, Any]) -> MCPToolResult:
        """MCP tool: process_payment — initiate payment with FlowRoute routing."""
        from prism.payment.application.dtos.payment_dto import PaymentRequestDTO

        request = PaymentRequestDTO(**args)
        result = await self._process_payment.execute(request)

        if result.success and result.value:
            return MCPToolResult(success=True, data=result.value.model_dump())
        return MCPToolResult(success=False, error=result.error or "Payment processing failed")

    async def _handle_capture_payment(self, args: dict[str, Any]) -> MCPToolResult:
        """MCP tool: capture_payment — capture an authorised payment."""
        payment_id = args.get("payment_id", "")
        result = await self._capture_payment.execute(payment_id)

        if result.success and result.value:
            return MCPToolResult(success=True, data=result.value.model_dump())
        return MCPToolResult(success=False, error=result.error or "Capture failed")

    async def _handle_refund_payment(self, args: dict[str, Any]) -> MCPToolResult:
        """MCP tool: refund_payment — refund a captured payment."""
        payment_id = args.get("payment_id", "")
        result = await self._refund_payment.execute(payment_id)

        if result.success and result.value:
            return MCPToolResult(success=True, data=result.value.model_dump())
        return MCPToolResult(success=False, error=result.error or "Refund failed")

    async def _handle_check_bnpl(self, args: dict[str, Any]) -> MCPToolResult:
        """MCP tool: check_bnpl — check BNPL eligibility for a customer."""
        from prism.shared.domain.value_objects import Currency, Money

        amount = Money(
            amount=args.get("amount", 0),
            currency=Currency(args.get("currency", "USD")),
        )
        customer_id = args.get("customer_id", "")

        eligibility = await self._bnpl_port.check_eligibility(amount, customer_id)

        return MCPToolResult(
            success=True,
            data={
                "eligible": eligibility.eligible,
                "options": [
                    {
                        "provider": opt.provider.value,
                        "installments": opt.installments,
                        "interest_rate": opt.interest_rate,
                        "min_amount": opt.min_amount.amount,
                        "max_amount": opt.max_amount.amount,
                        "currency": opt.min_amount.currency.value,
                    }
                    for opt in eligibility.options
                ],
            },
        )

    # -- Resource Implementations ----------------------------------------

    async def _handle_get_payment_status(self, args: dict[str, Any]) -> MCPToolResult:
        """MCP resource: payment://status/{payment_id}"""
        payment_id = args.get("payment_id", "")
        result = await self._get_payment_status.execute(payment_id=payment_id)

        if result.success and result.data:
            return MCPToolResult(success=True, data=result.data.model_dump())
        return MCPToolResult(success=False, error=result.error or "Payment not found")

    async def _handle_get_fx_comparison(self, args: dict[str, Any]) -> MCPToolResult:
        """MCP resource: payment://fx/{source}/{target}"""
        result = await self._get_fx_comparison.execute(
            source_currency=args.get("source_currency", ""),
            target_currency=args.get("target_currency", ""),
            amount=args.get("amount", 1000.0),
        )

        if result.success and result.data:
            return MCPToolResult(success=True, data=result.data.model_dump())
        return MCPToolResult(success=False, error=result.error or "FX comparison failed")

    # -- Metadata --------------------------------------------------------

    def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP tool metadata for discovery."""
        return [
            {
                "name": "process_payment",
                "description": "Initiate a payment with FlowRoute multi-PSP routing",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "tenant_id": {"type": "string"},
                        "amount": {"type": "number"},
                        "currency": {"type": "string"},
                        "customer_currency": {"type": "string"},
                        "settlement_currency": {"type": "string"},
                        "card_token": {"type": "string"},
                    },
                    "required": ["order_id", "tenant_id", "amount", "currency",
                                 "customer_currency", "settlement_currency", "card_token"],
                },
            },
            {
                "name": "capture_payment",
                "description": "Capture a previously authorised payment",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "payment_id": {"type": "string"},
                    },
                    "required": ["payment_id"],
                },
            },
            {
                "name": "refund_payment",
                "description": "Refund a captured payment",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "payment_id": {"type": "string"},
                    },
                    "required": ["payment_id"],
                },
            },
            {
                "name": "check_bnpl",
                "description": "Check Buy Now Pay Later eligibility for a customer and amount",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number"},
                        "currency": {"type": "string"},
                        "customer_id": {"type": "string"},
                    },
                    "required": ["amount", "currency", "customer_id"],
                },
            },
        ]

    def list_resources(self) -> list[dict[str, Any]]:
        """Return MCP resource metadata for discovery."""
        return [
            {
                "uri": "payment://status/{payment_id}",
                "name": "Payment Status",
                "description": "Current status and details of a payment",
                "mimeType": "application/json",
            },
            {
                "uri": "payment://fx/{source}/{target}",
                "name": "FX Rate Comparison",
                "description": "Compare FX rates across providers for a currency pair",
                "mimeType": "application/json",
            },
        ]
