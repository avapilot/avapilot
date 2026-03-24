"""
Network configuration — Avalanche C-Chain and Subnets.
"""

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
}

# Well-known Avalanche tokens
AVALANCHE_TOKENS = {
    "WAVAX": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",
    "USDC": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
    "USDT": "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7",
    "BTC.b": "0x152b9d0FdC40C096DE345096A65E5BCd1545DBF7",
    "WETH.e": "0x49D5c2BdFfac6CE2BFDb6640F4F80f226bc10bAB",
    "JOE": "0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd",
    "QI": "0x8729438EB15e2C8B576fCc6AeCdA6A148776C0F5",
}

FUJI_TOKENS = {
    "WAVAX": "0xd00ae08403B9bbb9124bB305C09058E32C39A48c",
    "USDC": "0x5425890298aed601595a70AB815c96711a31Bc65",
}


def get_token_address(symbol: str, chain: str = "avalanche") -> str:
    """Get token address for the given chain."""
    tokens = FUJI_TOKENS if chain == "fuji" else AVALANCHE_TOKENS
    addr = tokens.get(symbol.upper())
    if not addr:
        # Fallback to mainnet tokens
        addr = AVALANCHE_TOKENS.get(symbol.upper())
    if not addr:
        raise ValueError(f"Unknown token '{symbol}' on {chain}")
    return addr


# Well-known Avalanche dApps
AVALANCHE_DAPPS = {
    "trader_joe_router": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4",
    "trader_joe_router_v2": "0xb4315e873dBcf96Ffd0acd8EA43f689D8c20fB30",
    "pangolin_router": "0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106",
    "benqi_comptroller": "0x486Af39519B4Dc9a7fCcd318217352830D8B1cf8",
    "aave_pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
    "stargate_router": "0x45A01E4e04F14f7A4a6702c74187c5F6222033cd",
}


# P-Chain RPC endpoints
PCHAIN_RPC = {
    "mainnet": "https://api.avax.network/ext/bc/P",
    "fuji": "https://api.avax-test.network/ext/bc/P",
}

# Info API endpoints
INFO_API = {
    "mainnet": "https://api.avax.network/ext/info",
    "fuji": "https://api.avax-test.network/ext/info",
}

# Glacier Data API
GLACIER_API_URL = "https://glacier-api.avax.network"


def get_chain_config(chain: str = "avalanche") -> dict:
    """Get chain configuration by name."""
    chain = chain.lower()
    if chain not in CHAINS:
        available = ", ".join(CHAINS.keys())
        raise ValueError(f"Unknown chain '{chain}'. Available: {available}")
    return CHAINS[chain]
