"""
PRISM Demo Mocks — In-Memory Infrastructure Adapters

Mock implementations for all port interfaces across PRISM bounded contexts.
Each module corresponds to one bounded context and provides realistic
luxury retail data for demonstration purposes.
"""

from prism.demo.mocks.catalogue_mocks import (
    InMemoryBrandRepository,
    InMemoryProductRepository,
    MockCatalogueEnrichmentPort,
    MockEmbeddingPort,
)
from prism.demo.mocks.intelligence_mocks import (
    MockAttributeExtractor,
    MockDescriptionGenerator,
    MockEmbeddingGenerator,
    MockImageQuality,
    MockVectorIndex,
)
from prism.demo.mocks.discovery_mocks import (
    MockHybridSearch,
    MockImageSearch,
    MockPersonalisation,
    MockVectorSearch,
)
from prism.demo.mocks.tryon_mocks import (
    MockBodyExtractor,
    MockCompositor,
    MockStyleMatcher,
)
from prism.demo.mocks.commerce_mocks import (
    MockGoogleShopping,
    MockInventory,
    MockUCPInbound,
    MockUCPOutbound,
)
from prism.demo.mocks.payment_mocks import (
    InMemoryPaymentRepository,
    MockBNPL,
    MockFXRate,
    MockPSP,
    MockRoutingRuleRepository,
)
from prism.demo.mocks.agentic_cx_mocks import (
    InMemoryConversationRepository,
    MockAgentLLM,
    MockChannelAdapter,
    MockCustomerProfile,
    MockLongTermMemory,
    MockSessionMemory,
    MockToolExecutor,
)
from prism.demo.mocks.gateway_mocks import (
    MockAPIKeyRepository,
    MockPIMConnector,
    MockRateLimiter,
    MockTenantConfig,
    MockWebhookDispatch,
)

__all__ = [
    # Catalogue
    "InMemoryProductRepository",
    "InMemoryBrandRepository",
    "MockCatalogueEnrichmentPort",
    "MockEmbeddingPort",
    # Intelligence
    "MockAttributeExtractor",
    "MockDescriptionGenerator",
    "MockEmbeddingGenerator",
    "MockVectorIndex",
    "MockImageQuality",
    # Discovery
    "MockVectorSearch",
    "MockImageSearch",
    "MockHybridSearch",
    "MockPersonalisation",
    # Try-On
    "MockBodyExtractor",
    "MockCompositor",
    "MockStyleMatcher",
    # Commerce
    "MockUCPInbound",
    "MockUCPOutbound",
    "MockGoogleShopping",
    "MockInventory",
    # Payment
    "MockPSP",
    "MockFXRate",
    "MockRoutingRuleRepository",
    "InMemoryPaymentRepository",
    "MockBNPL",
    # Agentic CX
    "MockAgentLLM",
    "MockToolExecutor",
    "InMemoryConversationRepository",
    "MockCustomerProfile",
    "MockSessionMemory",
    "MockLongTermMemory",
    "MockChannelAdapter",
    # Gateway
    "MockAPIKeyRepository",
    "MockTenantConfig",
    "MockRateLimiter",
    "MockWebhookDispatch",
    "MockPIMConnector",
]
