"""
PRISM Payment Bounded Context

Payment Orchestration layer (Layer 6) for the Unified Commerce Intelligence Platform.
Encompasses FlowRoute (multi-PSP routing) and BARQ (reconciliation) capabilities
for luxury retail payment processing.

Architectural Role:
- Owns the Payment aggregate and all payment lifecycle state transitions
- FlowRoute: intelligent multi-PSP routing with cascade failover
- Provides FX rate comparison, DCC, and BNPL eligibility across providers
- Publishes domain events consumed by Commerce, Intelligence, and Reconciliation contexts
- MCP server exposes payment tools and resources
"""
