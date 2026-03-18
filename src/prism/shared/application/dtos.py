"""
Shared Application — Base DTOs and Command/Query Results

Architectural Intent:
- Typed result wrappers for all use case returns
- Success/failure semantics without exceptions for expected business errors
- Pydantic models for structured AI output schemas
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


@dataclass(frozen=True)
class CommandResult(Generic[T]):
    """Result of a command (write) operation."""

    success: bool
    value: T | None = None
    error: str | None = None
    error_code: str | None = None

    @staticmethod
    def ok(value: T) -> CommandResult[T]:
        return CommandResult(success=True, value=value)

    @staticmethod
    def fail(error: str, code: str = "UNKNOWN") -> CommandResult[Any]:
        return CommandResult(success=False, error=error, error_code=code)


@dataclass(frozen=True)
class QueryResult(Generic[T]):
    """Result of a query (read) operation."""

    success: bool
    data: T | None = None
    error: str | None = None
    total_count: int = 0

    @staticmethod
    def ok(data: T, total_count: int = 0) -> QueryResult[T]:
        return QueryResult(success=True, data=data, total_count=total_count)

    @staticmethod
    def empty() -> QueryResult[Any]:
        return QueryResult(success=True, data=None, total_count=0)

    @staticmethod
    def fail(error: str) -> QueryResult[Any]:
        return QueryResult(success=False, error=error)


class PaginationParams(BaseModel):
    """Pagination parameters for list queries."""

    offset: int = 0
    limit: int = 50
    cursor: str | None = None


class TenantContext(BaseModel):
    """Tenant context passed through all application operations."""

    tenant_id: str
    brand_name: str = ""
    locale: str = "en"
