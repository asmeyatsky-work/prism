"""
PRISM Demo Infrastructure — In-Memory Mock Adapters

Provides fully local, in-memory implementations of all infrastructure ports
across PRISM's 8 bounded contexts. These mocks replace GCP/external service
dependencies so the entire platform runs locally for demonstrations.

Usage:
    from prism.demo.mocks.catalogue_mocks import InMemoryProductRepository
    repo = InMemoryProductRepository()
"""
