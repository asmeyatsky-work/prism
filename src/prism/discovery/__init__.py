"""
PRISM Discovery Bounded Context

The multimodal discovery layer (Layer 3) for the Unified Commerce Intelligence
Platform. Provides text, image, and hybrid search across luxury product
catalogues with personalisation re-ranking and faceted navigation.

Architectural Role:
- Owns SearchSession aggregate and search execution lifecycle
- Provides MCP server for search operations (tools=writes, resources=reads)
- Consumes product data from Catalogue context via domain events
- Publishes discovery events consumed by Intelligence and Agentic CX contexts
"""
