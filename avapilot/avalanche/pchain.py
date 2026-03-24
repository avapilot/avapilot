"""
Avalanche P-Chain JSON-RPC client.

Wraps the Platform VM API for subnet, validator, and staking queries.
Docs: https://docs.avax.network/api-reference/p-chain/api
"""

import requests
from avapilot.runtime.config import PCHAIN_RPC


PCHAIN_FALLBACK_RPCS = [
    "https://avalanche-p-chain-rpc.publicnode.com",
]

def _rpc(method: str, params: dict | None = None, endpoint: str | None = None) -> dict:
    """Make a JSON-RPC call to the P-Chain with fallback RPCs."""
    primary = endpoint or PCHAIN_RPC["mainnet"]
    urls = [primary]
    if primary == PCHAIN_RPC["mainnet"]:
        urls.extend(PCHAIN_FALLBACK_RPCS)
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {},
    }
    
    last_error = None
    for url in urls:
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                last_error = RuntimeError(f"P-Chain RPC error: {data[chr(39)+'error'+chr(39)]}")
                continue
            return data.get("result", {})
        except Exception as e:
            last_error = e
            continue
    raise last_error or RuntimeError("All P-Chain RPCs failed")


def get_subnets(endpoint: str | None = None) -> list[dict]:
    """List all subnets on the network."""
    result = _rpc("platform.getSubnets", {}, endpoint)
    return result.get("subnets", [])


def get_current_validators(
    subnet_id: str | None = None,
    limit: int | None = None,
    endpoint: str | None = None,
) -> list[dict]:
    """List current validators, optionally filtered by subnet."""
    params = {}
    if subnet_id:
        params["subnetID"] = subnet_id
    if limit:
        params["limit"] = str(limit)
    result = _rpc("platform.getCurrentValidators", params, endpoint)
    return result.get("validators", [])


def get_pending_validators(
    subnet_id: str | None = None,
    endpoint: str | None = None,
) -> list[dict]:
    """List pending validators."""
    params = {}
    if subnet_id:
        params["subnetID"] = subnet_id
    result = _rpc("platform.getPendingValidators", params, endpoint)
    return result.get("validators", [])


def get_blockchains(endpoint: str | None = None) -> list[dict]:
    """List all blockchains registered on the network."""
    result = _rpc("platform.getBlockchains", {}, endpoint)
    return result.get("blockchains", [])


def get_blockchain_status(blockchain_id: str, endpoint: str | None = None) -> str:
    """Get the status of a blockchain (Validating, Created, Preferred, etc.)."""
    result = _rpc(
        "platform.getBlockchainStatus",
        {"blockchainID": blockchain_id},
        endpoint,
    )
    return result.get("status", "Unknown")


def get_staking_asset_id(
    subnet_id: str | None = None,
    endpoint: str | None = None,
) -> str:
    """Get the asset ID used for staking on a subnet."""
    params = {}
    if subnet_id:
        params["subnetID"] = subnet_id
    result = _rpc("platform.getStakingAssetID", params, endpoint)
    return result.get("assetID", "")


def get_current_supply(
    subnet_id: str | None = None,
    endpoint: str | None = None,
) -> str:
    """Get current token supply (returned as string of nAVAX)."""
    params = {}
    if subnet_id:
        params["subnetID"] = subnet_id
    result = _rpc("platform.getCurrentSupply", params, endpoint)
    return result.get("supply", "0")


def get_height(endpoint: str | None = None) -> int:
    """Get the current P-Chain block height."""
    result = _rpc("platform.getHeight", {}, endpoint)
    return int(result.get("height", 0))


def get_min_stake(endpoint: str | None = None) -> dict:
    """Get minimum staking amounts for validators and delegators."""
    result = _rpc("platform.getMinStake", {}, endpoint)
    return {
        "minValidatorStake": result.get("minValidatorStake", "0"),
        "minDelegatorStake": result.get("minDelegatorStake", "0"),
    }


def get_total_stake(
    subnet_id: str | None = None,
    endpoint: str | None = None,
) -> str:
    """Get total amount staked on the network or a subnet."""
    params = {}
    if subnet_id:
        params["subnetID"] = subnet_id
    result = _rpc("platform.getTotalStake", params, endpoint)
    return result.get("stake", result.get("weight", "0"))
