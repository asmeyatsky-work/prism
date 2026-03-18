"""
Shared Infrastructure — Dependency Injection Container

Architectural Intent:
- Composition root for wiring ports to adapters
- All dependency resolution happens here, not in domain or application layers
- Supports singleton and transient lifecycles
- MCP tool schemas mirror port method signatures (skill2026 Rule 2)
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

T = TypeVar("T")


class DependencyContainer:
    """
    Simple DI container for wiring ports to infrastructure adapters.

    Used at the composition root to configure all bounded contexts.
    Supports singleton (shared instance) and factory (new instance per resolve).
    """

    def __init__(self) -> None:
        self._singletons: dict[type, Any] = {}
        self._factories: dict[type, Callable[..., Any]] = {}

    def register_singleton(self, interface: type[T], instance: T) -> None:
        self._singletons[interface] = instance

    def register_factory(self, interface: type[T], factory: Callable[..., T]) -> None:
        self._factories[interface] = factory

    def resolve(self, interface: type[T]) -> T:
        if interface in self._singletons:
            return self._singletons[interface]
        if interface in self._factories:
            instance = self._factories[interface]()
            return instance
        raise KeyError(f"No registration found for {interface.__name__}")

    def resolve_or_none(self, interface: type[T]) -> T | None:
        try:
            return self.resolve(interface)
        except KeyError:
            return None

    def has(self, interface: type) -> bool:
        return interface in self._singletons or interface in self._factories
