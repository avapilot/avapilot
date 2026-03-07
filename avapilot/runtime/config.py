"""
Network configuration — Avalanche mainnet/fuji + extensible to any EVM chain.
"""

import os

CHAINS = {
    "avalanche": {
        "name": "Avalanche C-Chain",
        "rpc_url": "https://api.avax.network/ext/bc/C/rpc",
        "chain_id": 43114,
        "explorer_api": "https://api.snowtrace.io/api",
        "explorer_url": "https://snowtrace.io",
        "native_token": "AVAX",
    },
    "fuji": {
        "name": "Avalanche Fuji Testnet",
        "rpc_url": "https://api.avax-test.network/ext/bc/C/rpc",
        "chain_id": 43113,
        "explorer_api": "https://api-testnet.snowtrace.io/api",
        "explorer_url": "https://testnet.snowtrace.io",
        "native_token": "AVAX",
    },
    "ethereum": {
        "name": "Ethereum Mainnet",
        "rpc_url": "https://eth.llamarpc.com",
        "chain_id": 1,
        "explorer_api": "https://api.etherscan.io/api",
        "explorer_url": "https://etherscan.io",
        "native_token": "ETH",
    },
}


def get_chain_config(chain: str) -> dict:
    """Get chain configuration by name."""
    chain = chain.lower()
    if chain not in CHAINS:
        available = ", ".join(CHAINS.keys())
        raise ValueError(f"Unknown chain '{chain}'. Available: {available}")
    return CHAINS[chain]
