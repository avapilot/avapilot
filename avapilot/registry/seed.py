"""Seed the registry with well-known Avalanche dApps and tokens."""

from __future__ import annotations

SEED_SERVICES = [
    {
        "name": "Trader Joe",
        "contracts": [
            {"address": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4", "label": "router"},
        ],
        "description": "The leading DEX on Avalanche — swap tokens, add liquidity",
        "category": "DeFi",
        "website": "https://traderjoexyz.com",
    },
    {
        "name": "Benqi",
        "contracts": [
            {"address": "0x486Af39519B4Dc9a7fCcd318217352830D8B1cf8", "label": "comptroller"},
        ],
        "description": "Lending and borrowing protocol on Avalanche",
        "category": "DeFi",
        "website": "https://benqi.fi",
    },
    {
        "name": "Aave V3",
        "contracts": [
            {"address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD", "label": "pool"},
        ],
        "description": "Decentralized lending and borrowing",
        "category": "DeFi",
        "website": "https://aave.com",
    },
    {
        "name": "USDC",
        "contracts": [
            {"address": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", "label": "token"},
        ],
        "description": "Native USDC stablecoin on Avalanche",
        "category": "Token",
    },
    {
        "name": "WAVAX",
        "contracts": [
            {"address": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7", "label": "token"},
        ],
        "description": "Wrapped AVAX — ERC-20 wrapper for native AVAX",
        "category": "Token",
    },
]


def seed_registry(registry) -> list[str]:
    """Seed the registry with known dApps. Returns list of names added.

    Skips services that already exist (by name).
    """
    added = []
    for svc in SEED_SERVICES:
        if registry.get_service(svc["name"]):
            continue
        try:
            registry.register(
                name=svc["name"],
                contracts=svc["contracts"],
                description=svc.get("description", ""),
                category=svc.get("category", ""),
                website=svc.get("website", ""),
            )
            added.append(svc["name"])
        except Exception as e:
            print(f"   Warning: failed to seed '{svc['name']}': {e}")
    return added
