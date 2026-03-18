"""
PRISM Commerce Bounded Context — UCP Connector & Commerce Protocol Layer (Layer 5)

Architectural Intent:
- Bridges Unified Commerce Platform (UCP) data with PRISM's AI-enriched product intelligence
- Manages bidirectional data flow: UCP -> PRISM enrichment -> UCP/Google Shopping
- Implements PRISM Commerce Event Schema (PCES) as the canonical commerce data format
- Event-driven architecture with Pub/Sub for catalogue change propagation
- MCP server exposes commerce tools and inventory/feed resources
"""
