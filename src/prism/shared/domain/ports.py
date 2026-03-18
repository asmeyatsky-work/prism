"""
Shared Domain — Base Repository Port

Architectural Intent:
- Generic repository port defines the contract for all aggregate persistence
- Implementations (BigQuery, Firestore, etc.) live in infrastructure
- Tenant-scoped by default — all queries require TenantId
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from prism.shared.domain.entities import AggregateRoot
from prism.shared.domain.value_objects import TenantId

T = TypeVar("T", bound=AggregateRoot, covariant=True)
T_contra = TypeVar("T_contra", bound=AggregateRoot, contravariant=True)


class RepositoryPort(Protocol[T]):
    """Generic repository port for aggregate persistence."""

    async def get_by_id(self, id: str, tenant_id: TenantId) -> T | None: ...

    async def save(self, entity: AggregateRoot, tenant_id: TenantId) -> None: ...

    async def delete(self, id: str, tenant_id: TenantId) -> None: ...
