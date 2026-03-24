from __future__ import annotations
"""
Avalanche-specific helpers — well-known dApps, token metadata, subnet support.
"""

from ..runtime.config import AVALANCHE_DAPPS, AVALANCHE_TOKENS

# Human-friendly descriptions for known Avalanche contracts
KNOWN_CONTRACTS = {
    "0x60aE616a2155Ee3d9A68541Ba4544862310933d4": {
        "name": "Trader Joe Router",
        "description": "The main DEX on Avalanche — swap tokens, add/remove liquidity",
        "tags": ["dex", "swap", "liquidity", "defi"],
    },
    "0xb4315e873dBcf96Ffd0acd8EA43f689D8c20fB30": {
        "name": "Trader Joe Router V2 (LB)",
        "description": "Trader Joe Liquidity Book router — concentrated liquidity AMM",
        "tags": ["dex", "swap", "concentrated-liquidity", "defi"],
    },
    "0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106": {
        "name": "Pangolin Router",
        "description": "Pangolin DEX router — community-driven AMM on Avalanche",
        "tags": ["dex", "swap", "defi"],
    },
    "0x486Af39519B4Dc9a7fCcd318217352830D8B1cf8": {
        "name": "Benqi Comptroller",
        "description": "Benqi lending protocol — supply assets to earn yield, borrow against collateral",
        "tags": ["lending", "borrowing", "defi", "yield"],
    },
    "0x794a61358D6845594F94dc1DB02A252b5b4814aD": {
        "name": "Aave V3 Pool",
        "description": "Aave V3 on Avalanche — lending and borrowing protocol",
        "tags": ["lending", "borrowing", "defi"],
    },
    "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E": {
        "name": "USDC",
        "description": "Native USDC stablecoin on Avalanche",
        "tags": ["token", "stablecoin", "erc20"],
    },
    "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7": {
        "name": "WAVAX",
        "description": "Wrapped AVAX — ERC-20 wrapper for the native AVAX token",
        "tags": ["token", "wrapped", "erc20"],
    },
}


def get_known_contract_info(address: str) -> dict | None:
    """Return metadata for well-known Avalanche contracts, or None."""
    return KNOWN_CONTRACTS.get(address)


def resolve_dapp_name(name: str) -> str | None:
    """Resolve a dApp name to a contract address. e.g., 'trader_joe_router' → '0x60a...'"""
    return AVALANCHE_DAPPS.get(name.lower().replace(" ", "_").replace("-", "_"))
