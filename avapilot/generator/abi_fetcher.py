"""
ABI fetcher — retrieves contract ABI and metadata from block explorers.
"""

import json
from ..runtime.evm import fetch_abi, fetch_source_code
from ..runtime.config import get_chain_config


def fetch_contract_data(contract_address: str, chain: str = "avalanche", api_key: str = "") -> dict:
    """
    Fetch all available data for a contract.
    
    Returns:
        {
            "address": "0x...",
            "chain": "avalanche",
            "abi": [...],
            "source_code": "..." or None,
            "verified": True/False,
        }
    """
    cfg = get_chain_config(chain)
    
    abi = fetch_abi(contract_address, cfg["explorer_api"], api_key)
    source = fetch_source_code(contract_address, cfg["explorer_api"], api_key)
    
    return {
        "address": contract_address,
        "chain": chain,
        "chain_name": cfg["name"],
        "rpc_url": cfg["rpc_url"],
        "chain_id": cfg["chain_id"],
        "explorer_url": cfg["explorer_url"],
        "native_token": cfg["native_token"],
        "abi": abi,
        "source_code": source,
        "verified": source is not None,
    }
