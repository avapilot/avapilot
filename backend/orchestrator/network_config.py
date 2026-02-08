"""
Network Configuration — Avalanche mainnet / fuji testnet
Set NETWORK=mainnet or NETWORK=fuji (default) in .env
"""

import os
from dotenv import load_dotenv

load_dotenv()

NETWORK = os.getenv("NETWORK", "fuji").lower()

_NETWORKS = {
    "fuji": {
        "name": "Avalanche Fuji Testnet",
        "rpc_url": "https://api.avax-test.network/ext/bc/C/rpc",
        "chain_id": 43113,
        "explorer_api": "https://api-testnet.snowtrace.io/api",
        "explorer_url": "https://testnet.snowtrace.io",
        "tokens": {
            "WAVAX": "0x1d308089a2d1ced3f1ce36b1fcaf815b07217be3",
            "USDC": "0x5425890298aed601595a70AB815c96711a31Bc65",
        },
    },
    "mainnet": {
        "name": "Avalanche C-Chain",
        "rpc_url": "https://api.avax.network/ext/bc/C/rpc",
        "chain_id": 43114,
        "explorer_api": "https://api.snowtrace.io/api",
        "explorer_url": "https://snowtrace.io",
        "tokens": {
            "WAVAX": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",
            "USDC": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        },
    },
}

if NETWORK not in _NETWORKS:
    raise ValueError(f"Unknown NETWORK={NETWORK}. Must be 'fuji' or 'mainnet'.")

_cfg = _NETWORKS[NETWORK]

NETWORK_NAME: str = _cfg["name"]
RPC_URL: str = _cfg["rpc_url"]
CHAIN_ID: int = _cfg["chain_id"]
EXPLORER_API_URL: str = _cfg["explorer_api"]
EXPLORER_URL: str = _cfg["explorer_url"]
EXPLORER_API_KEY: str = os.getenv("SNOWTRACE_API_KEY", "placeholder")
TOKEN_ADDRESSES: dict = _cfg["tokens"]

print(f"[NETWORK] {NETWORK_NAME} (chain_id={CHAIN_ID})")
