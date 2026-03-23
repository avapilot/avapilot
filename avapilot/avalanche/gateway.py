"""
AvaPilot Gateway — mode-based MCP server factory.

Modes:
  read  — safe queries only, no wallet needed (default)
  trade — read + send/swap/approve tokens (wallet required)
  full  — trade + deploy/write arbitrary contracts (power user)

Registered services from the ServiceRegistry are loaded as dynamic tools.
"""

from __future__ import annotations

import json
from mcp.server.fastmcp import FastMCP

from avapilot.avalanche import tools_read, tools_trade, tools_full

MODES = {"read", "trade", "full"}

MODE_DESCRIPTIONS = {
    "read": "AvaPilot Avalanche Gateway (read-only)",
    "trade": "AvaPilot Avalanche Gateway (trade)",
    "full": "AvaPilot Avalanche Gateway (full)",
}


def create_gateway(mode: str = "read", registry_path: str | None = None) -> FastMCP:
    """Create an MCP server with the requested capability level.

    Modes are additive:
      read  → read tools only
      trade → read + trade tools
      full  → read + trade + full tools

    All registered services from the ServiceRegistry are loaded as dynamic tools.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}. Choose from: {', '.join(sorted(MODES))}")

    mcp = FastMCP(MODE_DESCRIPTIONS[mode])

    # 1. Built-in tools (always present)
    tools_read.register(mcp)

    if mode in ("trade", "full"):
        tools_trade.register(mcp)

    if mode == "full":
        tools_full.register(mcp)

    # 2. Dynamic tools from registered services
    try:
        from avapilot.registry import ServiceRegistry
        registry = ServiceRegistry(registry_path)
        services = registry.list_services()
        for service in services:
            _register_service_tools(mcp, service, mode)
        # 3. Service discovery tools
        _register_discovery_tools(mcp, registry)
    except Exception:
        # Registry unavailable — gateway still works with built-in tools
        pass

    return mcp


def _register_service_tools(mcp: FastMCP, service, mode: str):
    """Dynamically register MCP tools for every function in a service's contracts."""
    from avapilot.registry.store import _build_tool_defs

    tool_defs = _build_tool_defs(service)

    for td in tool_defs:
        is_read = td["is_read"]

        # Only include write tools in trade/full modes
        if not is_read and mode == "read":
            continue

        _create_dynamic_tool(mcp, td, service)


def _create_dynamic_tool(mcp: FastMCP, td: dict, service):
    """Create and register a single dynamic MCP tool from a tool definition."""
    from avapilot.runtime.config import get_chain_config
    from avapilot.runtime.evm import read_contract, build_transaction

    tool_name = td["tool_name"]
    func_name = td["function_name"]
    contract_address = td["contract_address"]
    chain = td["chain"]
    abi_item = td["abi_item"]
    is_read = td["is_read"]
    params = td["parameters"]

    # Build description
    param_str = ", ".join(f"{p['name']}: {p['type']}" for p in params)
    desc = f"{td['description']}({param_str})"
    if is_read:
        desc += " [read]"
    else:
        desc += " [write]"

    # We need the full ABI for the contract — find it from the service
    contract_abi = None
    for c in service.contracts:
        if c.address == contract_address:
            contract_abi = c.abi
            break

    if not contract_abi:
        return

    # Build the tool function dynamically
    if is_read:
        def make_read_tool(_fname, _addr, _abi, _chain):
            def tool_fn(**kwargs) -> str:
                cfg = get_chain_config(_chain)
                args = list(kwargs.values())
                try:
                    result = read_contract(cfg["rpc_url"], _addr, _abi, _fname, args)
                    return json.dumps({"success": True, "result": str(result)})
                except Exception as e:
                    return json.dumps({"success": False, "error": str(e)})
            tool_fn.__name__ = tool_name
            tool_fn.__doc__ = desc
            return tool_fn

        fn = make_read_tool(func_name, contract_address, contract_abi, chain)
    else:
        def make_write_tool(_fname, _addr, _abi):
            def tool_fn(**kwargs) -> str:
                args = list(kwargs.values())
                try:
                    tx = build_transaction(_addr, _abi, _fname, args)
                    return json.dumps({
                        "success": True,
                        "transaction": tx,
                        "description": f"Call {_fname} on {_addr}",
                    })
                except Exception as e:
                    return json.dumps({"success": False, "error": str(e)})
            tool_fn.__name__ = tool_name
            tool_fn.__doc__ = desc
            return tool_fn

        fn = make_write_tool(func_name, contract_address, contract_abi)

    mcp.tool(name=tool_name, description=desc)(fn)


def _register_discovery_tools(mcp: FastMCP, registry):
    """Register service discovery tools so the AI can browse registered services."""

    @mcp.tool(
        name="list_services",
        description="List all registered services on AvaPilot. Optionally filter by category or search term.",
    )
    def list_services(category: str = "", search: str = "") -> str:
        services = registry.list_services(
            category=category or None,
            search=search or None,
        )
        result = []
        for s in services:
            result.append({
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "read_tools": s.total_read_tools,
                "write_tools": s.total_write_tools,
                "contracts": len(s.contracts),
            })
        return json.dumps(result)

    @mcp.tool(
        name="service_info",
        description="Get detailed information about a registered service by name.",
    )
    def service_info(name: str) -> str:
        s = registry.get_service(name)
        if not s:
            return json.dumps({"error": f"Service '{name}' not found"})
        contracts = []
        for c in s.contracts:
            contracts.append({
                "address": c.address,
                "label": c.label,
                "type": c.contract_type,
                "read_functions": len(c.read_functions),
                "write_functions": len(c.write_functions),
            })
        return json.dumps({
            "name": s.name,
            "description": s.description,
            "category": s.category,
            "website": s.website,
            "contracts": contracts,
            "total_read_tools": s.total_read_tools,
            "total_write_tools": s.total_write_tools,
        })

    @mcp.tool(
        name="service_tools",
        description="List all available tools for a registered service.",
    )
    def service_tools(name: str) -> str:
        tools = registry.get_tools_for_service(name)
        if not tools:
            return json.dumps({"error": f"No tools found for '{name}'"})
        result = []
        for t in tools:
            result.append({
                "tool_name": t["tool_name"],
                "function": t["function_name"],
                "is_read": t["is_read"],
                "parameters": t["parameters"],
                "description": t["description"],
            })
        return json.dumps(result)
