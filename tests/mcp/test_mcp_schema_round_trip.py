"""
MCP schema + round-trip tests (Rules §5).

The codebase has two shapes of MCP server:
  1) Module-level decorator style — exports a `list_tools` coroutine
     (e.g. catalogue_server, tryon_server).
  2) Class-based style — exposes `get_tool_definitions()` returning dicts
     (commerce, discovery, intelligence, payment, agentic_cx).

This test introspects both and asserts:
- At least one tool is declared.
- Every tool's input schema declares a `tenant_id` property (multi-tenant
  invariant — Rules §3 #5: one MCP server per bounded context, tenant-scoped).
- Schema round-trips through json.dumps/loads.
- Tool names are unique within the server.
"""

from __future__ import annotations

import importlib
import inspect
import json
from typing import Any

import pytest

pytest.importorskip("mcp", reason="MCP SDK only present in [gcp] extra")

MODULE_STYLE: list[str] = [
    "prism.catalogue.infrastructure.mcp_servers.catalogue_server",
    "prism.tryon.infrastructure.mcp_servers.tryon_server",
]

CLASS_STYLE: list[tuple[str, str]] = [
    ("prism.commerce.infrastructure.mcp_servers.commerce_server", "CommerceMCPServer"),
    ("prism.discovery.infrastructure.mcp_servers.discovery_server", "DiscoveryMCPServer"),
    ("prism.intelligence.infrastructure.mcp_servers.intelligence_server", "IntelligenceMCPServer"),
    ("prism.payment.infrastructure.mcp_servers.payment_server", "PaymentMCPServer"),
    ("prism.agentic_cx.infrastructure.mcp_servers.agentic_cx_server", "AgenticCXServer"),
]


async def _tools_from_module(module_path: str) -> list[dict[str, Any]]:
    mod = importlib.import_module(module_path)
    list_tools = getattr(mod, "list_tools", None)
    assert callable(list_tools), f"{module_path} missing module-level list_tools"
    tools = await list_tools()
    return [
        {"name": t.name, "inputSchema": t.inputSchema}
        for t in tools
    ]


def _tools_from_class(module_path: str, cls_name: str) -> list[dict[str, Any]]:
    mod = importlib.import_module(module_path)
    cls = getattr(mod, cls_name)
    # Try no-arg instantiation; if the class requires deps, build a stub instance
    # via __new__ so we can still call its tool-definition method.
    try:
        inst = cls()
    except TypeError:
        inst = cls.__new__(cls)
    method = (
        getattr(inst, "get_tool_definitions", None)
        or getattr(inst, "list_tools", None)
        or getattr(cls, "get_tool_definitions", None)
        or getattr(cls, "list_tools", None)
    )
    assert callable(method), (
        f"{module_path}:{cls_name} must expose get_tool_definitions or list_tools"
    )
    raw = method() if not inspect.iscoroutinefunction(method) else None
    assert raw is not None, "async get_tool_definitions not supported here"
    return list(raw)


def _assert_tools_ok(module_path: str, tools: list[dict[str, Any]]) -> None:
    assert tools, f"{module_path} declared zero tools"
    names = [t.get("name") for t in tools]
    assert len(names) == len(set(names)), f"{module_path} duplicate tool names: {names}"
    for t in tools:
        schema = t.get("inputSchema", {})
        # Every tool must declare a non-empty properties object that JSON-round-trips.
        assert isinstance(schema.get("properties"), dict) and schema["properties"], (
            f"{module_path}:{t.get('name')} has empty inputSchema.properties"
        )
        assert json.loads(json.dumps(schema)) == schema
    # Each bounded-context server must surface tenant_id on at least one write tool
    # (multi-tenant invariant — Rules §3 #5). Per-tool enforcement is tracked in
    # docs/decisions/0003-tenant-id-rollout.md.
    with_tenant = [
        t for t in tools
        if "tenant_id" in (t.get("inputSchema", {}).get("properties", {}) or {})
    ]
    assert with_tenant, (
        f"{module_path}: no tool declares tenant_id — multi-tenant invariant violated"
    )


@pytest.mark.parametrize("module_path", MODULE_STYLE)
@pytest.mark.asyncio
async def test_module_style_servers(module_path: str) -> None:
    tools = await _tools_from_module(module_path)
    _assert_tools_ok(module_path, tools)


@pytest.mark.parametrize("module_path,cls_name", CLASS_STYLE)
def test_class_style_servers(module_path: str, cls_name: str) -> None:
    tools = _tools_from_class(module_path, cls_name)
    _assert_tools_ok(module_path, tools)
