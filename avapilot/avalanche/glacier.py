"""
Glacier Data API client for Avalanche.

REST wrapper for the Glacier indexer — balances, transfers, validators, L1 chains.
Docs: https://glacier-api.avax.network/api
"""

import requests
from avapilot.runtime.config import GLACIER_API_URL


def _get(path: str, params: dict | None = None) -> dict:
    """Make a GET request to the Glacier API."""
    url = f"{GLACIER_API_URL}{path}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


# --- Chains & Networks ---


def list_chains() -> list[dict]:
    """List all EVM chains tracked by Glacier (including L1s)."""
    data = _get("/v1/chains")
    return data.get("chains", [])


def list_blockchains(network: str = "mainnet") -> list[dict]:
    """List all blockchains on a network."""
    data = _get(f"/v1/networks/{network}/blockchains")
    return data.get("blockchains", [])


def get_chain_info(chain_id: str) -> dict:
    """Get details about a specific chain."""
    return _get(f"/v1/chains/{chain_id}")


# --- Validators ---


def list_validators(
    network: str = "mainnet",
    page_size: int = 10,
    page_token: str | None = None,
) -> dict:
    """List validators on the network."""
    params = {"pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token
    return _get(f"/v1/networks/{network}/validators", params)


# --- Balances ---


def get_erc20_balances(chain_id: str, address: str) -> dict:
    """Get ERC-20 token balances for an address."""
    return _get(f"/v1/chains/{chain_id}/addresses/{address}/balances:listErc20")


def get_native_balance(chain_id: str, address: str) -> dict:
    """Get native token balance for an address."""
    return _get(f"/v1/chains/{chain_id}/addresses/{address}/balances:getNative")


# --- Transfers & Transactions ---


def list_erc20_transfers(
    chain_id: str,
    address: str,
    page_size: int = 10,
    page_token: str | None = None,
) -> dict:
    """List ERC-20 token transfers for an address."""
    params = {"pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token
    return _get(
        f"/v1/chains/{chain_id}/addresses/{address}/transactions:listErc20",
        params,
    )


def list_transactions(
    chain_id: str,
    address: str,
    page_size: int = 10,
    page_token: str | None = None,
) -> dict:
    """List native token transactions for an address."""
    params = {"pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token
    return _get(
        f"/v1/chains/{chain_id}/addresses/{address}/transactions:listNative",
        params,
    )


# --- Blocks ---


def get_block(chain_id: str, block_id: str) -> dict:
    """Get block details by number or hash."""
    return _get(f"/v1/chains/{chain_id}/blocks/{block_id}")


# --- NFTs ---


def list_nfts(
    chain_id: str,
    address: str,
    page_size: int = 10,
    page_token: str | None = None,
) -> dict:
    """List ERC-721 NFTs owned by an address."""
    params = {"pageSize": page_size}
    if page_token:
        params["pageToken"] = page_token
    return _get(
        f"/v1/chains/{chain_id}/addresses/{address}/balances:listErc721",
        params,
    )
