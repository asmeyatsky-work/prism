"""
PRISM Catalogue Bounded Context

The data foundation layer for the Unified Commerce Intelligence Platform.
Manages product data ingestion, enrichment, taxonomy, and quality scoring
for luxury retail brands.

Architectural Role:
- Owns the canonical Product aggregate and PRISM Unified Product Schema (PUPS)
- Provides MCP server for product read/write operations
- Publishes domain events consumed by Discovery, Intelligence, and Try-On contexts
"""
