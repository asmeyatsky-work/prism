"""Commerce Domain Ports — Protocol-based contracts for infrastructure adapters."""

from prism.commerce.domain.ports.commerce_ports import (
    GoogleShoppingPort,
    InventoryPort,
    UCPInboundPort,
    UCPOutboundPort,
)

__all__ = [
    "GoogleShoppingPort",
    "InventoryPort",
    "UCPInboundPort",
    "UCPOutboundPort",
]
