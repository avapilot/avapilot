"""
AvaPilot Gateway — mode-based MCP server factory.

Architecture: Lazy Discovery
  - 30 built-in tools (network, validators, balances, gas, contracts)
  - 8 trade tools (send, swap, wrap, approve)
  - 2 full tools (deploy, write_contract)
  - 5 discovery tools (search, info, tools, call_service, call_read)
  
Total: ~45 tools max. AI discovers services via search, calls them via
call_service/call_read. No 200+ tool bloat.
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


def create_gateway(mode: str = "read", registry_path: str | None = None, chain: str = "avalanche") -> FastMCP:
    """Create an MCP server with lazy service discovery.

    Built-in tools are always loaded. Registered services are accessed
    via discovery tools (search → info → call), not loaded as 200+ tools.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}. Choose from: {', '.join(sorted(MODES))}")

    chain_label = "fuji testnet" if chain == "fuji" else "mainnet"
    mcp = FastMCP(f"{MODE_DESCRIPTIONS[mode]} [{chain_label}]")

    # 1. Built-in tools
    tools_read.register(mcp, chain=chain)
    if mode in ("trade", "full"):
        tools_trade.register(mcp, chain=chain)
    if mode == "full":
        tools_full.register(mcp, chain=chain)

    # 2. Lazy discovery + execution tools
    try:
        from avapilot.registry import ServiceRegistry
        registry = ServiceRegistry(registry_path)
        _register_lazy_tools(mcp, registry, mode, chain=chain)
    except Exception:
        pass

    return mcp


def _register_lazy_tools(mcp: FastMCP, registry, mode: str, chain: str = "avalanche"):
    """Register discovery and execution tools for lazy service access."""
    from avapilot.runtime.config import get_chain_config
    from avapilot.runtime.evm import read_contract, build_transaction

    @mcp.tool(
        name="gateway_info",
        description="Show current gateway configuration — network, mode, and chain. Check this before executing transactions.",
    )
    def gateway_info() -> str:
        """Returns the current gateway network and mode."""
        chain_name = "Fuji Testnet" if chain == "fuji" else "Avalanche Mainnet"
        chain_id = 43113 if chain == "fuji" else 43114
        return json.dumps({
            "network": chain_name,
            "chain": chain,
            "chain_id": chain_id,
            "mode": mode,
            "warning": "All transactions will be sent to " + chain_name,
        })

    @mcp.tool(
        name="search_services",
        description="Search registered Avalanche services (DeFi protocols, tokens, etc). Returns name, category, description, and tool counts. IMPORTANT: registered services are on mainnet by default. For testnet operations, use built-in tools (send_avax, wrap_avax) with chain=fuji.",
    )
    def search_services(query: str = "", category: str = "") -> str:
        """Search services by name/description or filter by category (DeFi, Token, NFT, Gaming, Infrastructure)."""
        services = registry.list_services(
            category=category or None,
            search=query or None,
        )
        result = []
        for s in services:
            result.append({
                "name": s.name,
                "category": s.category,
                "description": s.description,
                "read_functions": s.total_read_tools,
                "write_functions": s.total_write_tools,
            })
        if not result and not query and not category:
            return json.dumps({"message": "No services registered. Run: avapilot seed"})
        return json.dumps(result)

    @mcp.tool(
        name="service_info",
        description="Get detailed info about a specific registered service — contracts, functions, types.",
    )
    def service_info(service_name: str) -> str:
        """Get details about a service including its contracts and available functions."""
        s = registry.get_service(service_name)
        if not s:
            return json.dumps({"error": f"Service '{service_name}' not found. Use search_services to find available services."})
        contracts = []
        for c in s.contracts:
            contracts.append({
                "address": c.address,
                "label": c.label,
                "type": c.contract_type,
                "read_functions": c.read_functions,
                "write_functions": c.write_functions,
            })
        return json.dumps({
            "name": s.name,
            "description": s.description,
            "category": s.category,
            "website": s.website,
            "contracts": contracts,
        })

    @mcp.tool(
        name="service_functions",
        description="List all callable functions for a service with their parameter signatures. Use this to know what args to pass to call_service.",
    )
    def service_functions(service_name: str) -> str:
        """List every function for a service with parameter names and types."""
        s = registry.get_service(service_name)
        if not s:
            return json.dumps({"error": f"Service '{service_name}' not found."})
        
        functions = []
        for c in s.contracts:
            for item in c.abi:
                if item.get("type") != "function":
                    continue
                is_read = item.get("stateMutability") in ("view", "pure") or item.get("constant", False)
                inputs = []
                for inp in item.get("inputs", []):
                    inputs.append({
                        "name": inp.get("name") or f"arg{len(inputs)}",
                        "type": inp["type"],
                    })
                outputs = [o["type"] for o in item.get("outputs", [])]
                functions.append({
                    "name": item["name"],
                    "contract": c.label,
                    "is_read": is_read,
                    "inputs": inputs,
                    "outputs": outputs,
                })
        return json.dumps(functions)

    @mcp.tool(
        name="call_service",
        description="Call a read function on a registered service. Pass the service name, function name, and arguments as a JSON object. Returns the on-chain result.",
    )
    def call_service(service_name: str, function_name: str, args: str = "{}") -> str:
        """Call a read (view/pure) function on a registered service's contract.
        
        Args:
            service_name: Name of the registered service (e.g., "Trader Joe", "USDC")
            function_name: Contract function name (e.g., "balanceOf", "getAmountsOut")
            args: JSON object with function arguments (e.g., '{"account": "0x..."}')
        """
        s = registry.get_service(service_name)
        if not s:
            return json.dumps({"error": f"Service '{service_name}' not found. Use search_services to find available services."})
        
        # Parse args
        try:
            parsed_args = json.loads(args) if isinstance(args, str) else args
        except json.JSONDecodeError:
            return json.dumps({"error": f"Invalid JSON args: {args}"})
        
        # Find the function in the service's contracts
        for c in s.contracts:
            func_abi = next(
                (item for item in c.abi if item.get("name") == function_name and item.get("type") == "function"),
                None,
            )
            if func_abi:
                # Build ordered args from the parsed dict
                input_specs = func_abi.get("inputs", [])
                ordered_args = []
                for i, spec in enumerate(input_specs):
                    name = spec.get("name") or f"arg{i}"
                    val = parsed_args.get(name, parsed_args.get(f"arg{i}", ""))
                    ordered_args.append(val)
                
                cfg = get_chain_config(c.chain)
                try:
                    result = read_contract(cfg["rpc_url"], c.address, c.abi, function_name, ordered_args)
                    # Format result nicely
                    if isinstance(result, (list, tuple)):
                        result = [str(r) for r in result]
                    else:
                        result = str(result)
                    return json.dumps({
                        "success": True,
                        "service": service_name,
                        "function": function_name,
                        "result": result,
                    })
                except Exception as e:
                    return json.dumps({"success": False, "error": str(e)})
        
        return json.dumps({"error": f"Function '{function_name}' not found in {service_name}. Use service_functions to see available functions."})

    if mode in ("trade", "full"):
        @mcp.tool(
            name="send_service_tx",
            description="Execute a write function on a registered service. Builds, signs, and sends the transaction. Requires wallet. WARNING: registered services are on their registered chain (usually mainnet). The transaction will be sent to that chain.",
        )
        def send_service_tx(service_name: str, function_name: str, args: str = "{}", value_avax: float = 0) -> str:
            """Call a write (state-changing) function on a registered service.
            
            Args:
                service_name: Name of the registered service
                function_name: Contract function name (e.g., "transfer", "approve")
                args: JSON object with function arguments
                value_avax: AVAX to send with the transaction (default 0)
            """
            from avapilot.avalanche import wallet
            from avapilot.avalanche._helpers import to_token_units, from_token_units
            
            if not wallet.is_wallet_configured():
                return json.dumps({"error": "Wallet not configured. Set AVAPILOT_PRIVATE_KEY environment variable."})
            
            s = registry.get_service(service_name)
            if not s:
                return json.dumps({"error": f"Service '{service_name}' not found."})
            
            try:
                parsed_args = json.loads(args) if isinstance(args, str) else args
            except json.JSONDecodeError:
                return json.dumps({"error": f"Invalid JSON args: {args}"})
            
            for c in s.contracts:
                func_abi = next(
                    (item for item in c.abi if item.get("name") == function_name and item.get("type") == "function"),
                    None,
                )
                if func_abi:
                    # Safety: warn if service is on a different chain than expected
                    service_chain = c.chain or "avalanche"
                    
                    input_specs = func_abi.get("inputs", [])
                    ordered_args = []
                    for i, spec in enumerate(input_specs):
                        name = spec.get("name") or f"arg{i}"
                        ordered_args.append(parsed_args.get(name, parsed_args.get(f"arg{i}", "")))
                    
                    try:
                        value_wei = to_token_units(value_avax, 18) if value_avax else 0
                        tx = build_transaction(c.address, c.abi, function_name, ordered_args, value_wei=value_wei)
                        
                        # Add chain-specific fields and send
                        cfg = get_chain_config(c.chain)
                        tx_hash = wallet.sign_and_send(tx, chain=service_chain)
                        receipt = wallet.wait_for_receipt(tx_hash, chain=service_chain)
                        
                        return json.dumps({
                            "success": True,
                            "service": service_name,
                            "function": function_name,
                            "tx_hash": tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}",
                            "status": "confirmed" if receipt.get("status") == 1 else "reverted",
                            "gas_used": receipt.get("gasUsed"),
                        })
                    except Exception as e:
                        return json.dumps({"success": False, "error": str(e)})
            
            return json.dumps({"error": f"Function '{function_name}' not found in {service_name}."})
