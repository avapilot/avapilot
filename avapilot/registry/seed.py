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
        "name": "Pangolin",
        "contracts": [
            {"address": "0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106", "label": "router"},
        ],
        "description": "Community-driven DEX on Avalanche — swap, earn, stake",
        "category": "DeFi",
        "website": "https://pangolin.exchange",
    },
    {
        "name": "USDT.e",
        "contracts": [
            {"address": "0xc7198437980c041c805A1EDcbA50c1Ce5db95118", "label": "token"},
        ],
        "description": "Bridged Tether USD on Avalanche",
        "category": "Token",
    },
    {
        "name": "JOE Token",
        "contracts": [
            {"address": "0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd", "label": "token"},
        ],
        "description": "Governance token for Trader Joe DEX",
        "category": "Token",
        "website": "https://traderjoexyz.com",
    },
    {
        "name": "sAVAX",
        "contracts": [
            {"address": "0x2b2C81e08f1Af8835a78Bb2A90AE924ACE0eA4bE", "label": "token"},
        ],
        "description": "Benqi liquid staking — staked AVAX derivative",
        "category": "DeFi",
        "website": "https://benqi.fi",
    },
    {
        "name": "ggAVAX",
        "contracts": [
            {"address": "0xA25EaF2906FA1a3a13EdAc9B9657108Af7B703e3", "label": "token"},
        ],
        "description": "GoGoPool liquid staking — staked AVAX derivative",
        "category": "DeFi",
        "website": "https://gogopool.com",
    },
    {
        "name": "Stargate USDC Pool",
        "contracts": [
            {"address": "0x1205f31718499dBf1fCa446663B532Ef87481fe1", "label": "pool"},
        ],
        "description": "Stargate cross-chain USDC liquidity pool on Avalanche",
        "category": "DeFi",
        "website": "https://stargate.finance",
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
