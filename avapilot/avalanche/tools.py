"""
Built-in Avalanche MCP tools — no contract generation needed.

Provides instant access to P-Chain data, Glacier indexer, validators,
balances, L1 chains, and staking info via MCP.
"""

from mcp.server.fastmcp import FastMCP

from avapilot.avalanche import pchain, glacier

mcp = FastMCP("AvaPilot Avalanche Tools")


# ── Network Info ──────────────────────────────────────────────────────────


@mcp.tool()
def avalanche_network_info() -> dict:
    """Get Avalanche network overview: P-Chain height, current supply, and chain count."""
    try:
        height = pchain.get_height()
    except Exception:
        height = None

    try:
        supply_navax = pchain.get_current_supply()
        supply_avax = int(supply_navax) / 1e9
    except Exception:
        supply_avax = None

    try:
        blockchains = pchain.get_blockchains()
        chain_count = len(blockchains)
    except Exception:
        chain_count = None

    return {
        "network": "Avalanche Mainnet",
        "p_chain_height": height,
        "current_supply_avax": supply_avax,
        "blockchain_count": chain_count,
    }


@mcp.tool()
def avalanche_list_l1s() -> list[dict]:
    """List all Avalanche L1 chains tracked by Glacier."""
    try:
        chains = glacier.list_chains()
        return [
            {
                "chain_id": c.get("chainId"),
                "chain_name": c.get("chainName"),
                "network_token": c.get("networkToken", {}).get("symbol"),
                "rpc_url": c.get("rpcUrl"),
            }
            for c in chains
        ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def avalanche_get_l1_info(chain_id_or_name: str) -> dict:
    """Get details about a specific Avalanche L1 chain by chain ID or name."""
    # Try direct chain ID lookup first
    try:
        return glacier.get_chain_info(chain_id_or_name)
    except Exception:
        pass

    # Fall back to searching by name
    try:
        chains = glacier.list_chains()
        name_lower = chain_id_or_name.lower()
        for c in chains:
            if name_lower in c.get("chainName", "").lower():
                return c
        return {"error": f"No chain found matching '{chain_id_or_name}'"}
    except Exception as e:
        return {"error": str(e)}


# ── Validators & Staking ─────────────────────────────────────────────────


@mcp.tool()
def avalanche_list_validators(subnet_id: str | None = None, limit: int = 20) -> list[dict]:
    """List current Avalanche validators. Optionally filter by subnet ID."""
    try:
        validators = pchain.get_current_validators(subnet_id=subnet_id, limit=limit)
        return [
            {
                "node_id": v.get("nodeID"),
                "start_time": v.get("startTime"),
                "end_time": v.get("endTime"),
                "stake_amount": v.get("stakeAmount"),
                "uptime": v.get("uptime"),
                "connected": v.get("connected"),
            }
            for v in validators[:limit]
        ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def avalanche_validator_info(node_id: str) -> dict:
    """Get details about a specific validator by node ID."""
    try:
        validators = pchain.get_current_validators()
        for v in validators:
            if v.get("nodeID") == node_id:
                return {
                    "node_id": v.get("nodeID"),
                    "start_time": v.get("startTime"),
                    "end_time": v.get("endTime"),
                    "stake_amount": v.get("stakeAmount"),
                    "uptime": v.get("uptime"),
                    "connected": v.get("connected"),
                    "delegation_fee": v.get("delegationFee"),
                    "delegator_count": len(v.get("delegators", []) or []),
                }
        return {"error": f"Validator {node_id} not found"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def avalanche_staking_info() -> dict:
    """Get staking overview: min stake amounts, total staked, staking asset."""
    result = {}
    try:
        min_stake = pchain.get_min_stake()
        result["min_validator_stake_avax"] = int(min_stake["minValidatorStake"]) / 1e9
        result["min_delegator_stake_avax"] = int(min_stake["minDelegatorStake"]) / 1e9
    except Exception:
        pass

    try:
        total = pchain.get_total_stake()
        result["total_staked_avax"] = int(total) / 1e9
    except Exception:
        pass

    try:
        result["staking_asset_id"] = pchain.get_staking_asset_id()
    except Exception:
        pass

    return result


# ── Token & Balance Queries ───────────────────────────────────────────────


@mcp.tool()
def avalanche_get_balance(address: str, chain_id: str = "43114") -> dict:
    """Get native + ERC-20 token balances for an address on an Avalanche chain."""
    result = {}
    try:
        native = glacier.get_native_balance(chain_id, address)
        result["native"] = native
    except Exception as e:
        result["native_error"] = str(e)

    try:
        erc20 = glacier.get_erc20_balances(chain_id, address)
        result["erc20"] = erc20
    except Exception as e:
        result["erc20_error"] = str(e)

    return result


@mcp.tool()
def avalanche_get_nfts(address: str, chain_id: str = "43114") -> dict:
    """Get NFT holdings for an address on an Avalanche chain."""
    try:
        return glacier.list_nfts(chain_id, address)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def avalanche_token_transfers(address: str, chain_id: str = "43114") -> dict:
    """Get recent token transfers for an address on an Avalanche chain."""
    result = {}
    try:
        result["native_transfers"] = glacier.list_transactions(chain_id, address)
    except Exception as e:
        result["native_error"] = str(e)

    try:
        result["erc20_transfers"] = glacier.list_erc20_transfers(chain_id, address)
    except Exception as e:
        result["erc20_error"] = str(e)

    return result


# ── Cross-Chain ───────────────────────────────────────────────────────────


@mcp.tool()
def avalanche_list_blockchains() -> list[dict]:
    """List all blockchains registered on the Avalanche network."""
    try:
        blockchains = pchain.get_blockchains()
        return [
            {
                "id": bc.get("id"),
                "name": bc.get("name"),
                "subnet_id": bc.get("subnetID"),
                "vm_id": bc.get("vmID"),
            }
            for bc in blockchains
        ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def avalanche_get_blockchain_status(blockchain_id: str) -> dict:
    """Check the status of a specific blockchain (Validating, Created, etc.)."""
    try:
        status = pchain.get_blockchain_status(blockchain_id)
        return {"blockchain_id": blockchain_id, "status": status}
    except Exception as e:
        return {"error": str(e)}


# ── Server entry point ───────────────────────────────────────────────────


def run_server():
    """Start the built-in Avalanche MCP tools server."""
    mcp.run()


if __name__ == "__main__":
    run_server()
