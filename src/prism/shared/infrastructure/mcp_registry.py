"""
Shared Infrastructure — MCP Server Registry

Architectural Intent:
- Centralised configuration for all MCP servers in the PRISM platform
- Each bounded context registers its MCP server here
- Registry provides discovery and health checking
- Per skill2026 Principle 5: MCP-Native Integration Architecture

MCP Integration:
- This IS the registry pattern from skill2026 Pattern 3
- Each bounded context has at most one MCP server
- Tools = write operations, Resources = read operations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration for a single MCP server."""

    name: str
    module: str
    description: str
    transport: str = "stdio"
    url: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    tools: tuple[str, ...] = field(default=())
    resources: tuple[str, ...] = field(default=())


class MCPServerRegistry:
    """
    Registry of all MCP servers in the PRISM platform.

    Each bounded context registers its server during application bootstrap.
    The registry provides server discovery for MCP client adapters.
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}

    def register(self, config: MCPServerConfig) -> None:
        if config.name in self._servers:
            raise ValueError(f"MCP server '{config.name}' already registered")
        self._servers[config.name] = config

    def get(self, name: str) -> MCPServerConfig:
        if name not in self._servers:
            raise KeyError(f"MCP server '{name}' not found in registry")
        return self._servers[name]

    def list_servers(self) -> list[MCPServerConfig]:
        return list(self._servers.values())

    def to_config_dict(self) -> dict[str, Any]:
        """Export registry as MCP server configuration JSON."""
        return {
            "mcpServers": {
                config.name: self._server_to_dict(config)
                for config in self._servers.values()
            }
        }

    def _server_to_dict(self, config: MCPServerConfig) -> dict[str, Any]:
        if config.transport == "stdio":
            return {
                "command": "python",
                "args": ["-m", config.module],
                "env": config.env,
            }
        return {
            "url": config.url,
            "transport": config.transport,
        }
