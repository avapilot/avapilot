"""Seed the registry with well-known Avalanche dApps and tokens."""

from __future__ import annotations

SEED_SERVICES = [
    # ══════════════════════════════════════════════════════════════════
    # DEXs
    # ══════════════════════════════════════════════════════════════════
    {
        "name": "Trader Joe",
        "contracts": [
            {"address": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4", "label": "router-v1"},
            {"address": "0x9Ad6C38BE94206cA50bb0d90783181834C915012", "label": "factory-v1"},
            {"address": "0xb4315e873dBcf96Ffd0acd8EA43f689D8c20fB30", "label": "router-v2"},
        ],
        "description": "The leading DEX on Avalanche — swap tokens, add liquidity, LP pools",
        "category": "DeFi",
        "website": "https://traderjoexyz.com",
    },
    {
        "name": "Pangolin",
        "contracts": [
            {"address": "0xE54Ca86531e17Ef3616d22Ca28b0D458b6C89106", "label": "router"},
            {"address": "0xefa94DE7a4656D787667C749f7E1223D71E9FD88", "label": "factory"},
        ],
        "description": "Community-driven DEX — swap, earn, stake",
        "category": "DeFi",
        "website": "https://pangolin.exchange",
    },
    {
        "name": "Pharaoh Exchange",
        "contracts": [
            {"address": "0xAAA45c8F5ef92a000a121d102F4e89278a711Faa", "label": "router"},
        ],
        "description": "ve(3,3) DEX on Avalanche — concentrated liquidity",
        "category": "DeFi",
        "website": "https://pharaoh.exchange",
    },
    # ══════════════════════════════════════════════════════════════════
    # Lending / Borrowing
    # ══════════════════════════════════════════════════════════════════
    {
        "name": "Benqi Lending",
        "contracts": [
            {"address": "0x486Af39519B4Dc9a7fCcd318217352830D8B1cf8", "label": "comptroller"},
            {"address": "0x5C0401e81Bc07Ca70fAD469b451682c0d747Ef1c", "label": "qiAVAX"},
            {"address": "0xBEb5d47A3f720Ec0a390d04b4d41ED7d9688bC7F", "label": "qiUSDC"},
        ],
        "description": "Lend, borrow, and earn interest on Avalanche",
        "category": "DeFi",
        "website": "https://benqi.fi",
    },
    {
        "name": "Aave V3",
        "contracts": [
            {"address": "0x794a61358D6845594F94dc1DB02A252b5b4814aD", "label": "pool"},
            {"address": "0x69FA688f1Dc47d4B5d8029D5a35FB7a548310654", "label": "oracle"},
            {"address": "0x770ef9f4fe897e59daCc474EF11238303F9552b6", "label": "rewards"},
        ],
        "description": "Lend, borrow, and earn — the largest DeFi lending protocol",
        "category": "DeFi",
        "website": "https://aave.com",
    },
    # ══════════════════════════════════════════════════════════════════
    # Liquid Staking
    # ══════════════════════════════════════════════════════════════════
    {
        "name": "sAVAX",
        "contracts": [
            {"address": "0x2b2C81e08f1Af8835a78Bb2A90AE924ACE0eA4bE", "label": "token"},
        ],
        "description": "Benqi liquid staking — stake AVAX, get sAVAX",
        "category": "DeFi",
        "website": "https://benqi.fi",
    },
    {
        "name": "ggAVAX",
        "contracts": [
            {"address": "0xA25EaF2906FA1a3a13EdAc9B9657108Af7B703e3", "label": "token"},
        ],
        "description": "GoGoPool liquid staking — stake AVAX, get ggAVAX",
        "category": "DeFi",
        "website": "https://gogopool.com",
    },
    # ══════════════════════════════════════════════════════════════════
    # Yield / Aggregator
    # ══════════════════════════════════════════════════════════════════
    {
        "name": "Yield Yak",
        "contracts": [
            {"address": "0xC73DF1e68FC203F6E4b6270240D6f82A850e8D38", "label": "router"},
        ],
        "description": "Yield optimizer and DEX aggregator — auto-compound, best swap routes",
        "category": "DeFi",
        "website": "https://yieldyak.com",
    },
    # ══════════════════════════════════════════════════════════════════
    # Perpetuals / Derivatives
    # ══════════════════════════════════════════════════════════════════
    {
        "name": "GMX",
        "contracts": [
            {"address": "0x62edc0692BD897D2295872a9FFCac5425011c661", "label": "token"},
            {"address": "0xe1ae4d4b06A5Fe1fc288f6B4CD72f9F8323B107F", "label": "vault"},
            {"address": "0x5F719c2F1095F7B9996525dd69C688C7a6Cec963", "label": "router"},
        ],
        "description": "Decentralized perpetual exchange — leverage trade with low fees",
        "category": "DeFi",
        "website": "https://gmx.io",
    },
    # ══════════════════════════════════════════════════════════════════
    # Cross-chain / Bridge
    # ══════════════════════════════════════════════════════════════════
    {
        "name": "Stargate",
        "contracts": [
            {"address": "0x1205f31718499dBf1fCa446663B532Ef87481fe1", "label": "usdc-pool"},
            {"address": "0x45A01E4e04F14f7A4a6702c74187c5F6222033cd", "label": "router"},
        ],
        "description": "Cross-chain bridge — transfer tokens between chains via LayerZero",
        "category": "DeFi",
        "website": "https://stargate.finance",
    },
    # ══════════════════════════════════════════════════════════════════
    # Stablecoins / Major Tokens
    # ══════════════════════════════════════════════════════════════════
    {
        "name": "WAVAX",
        "contracts": [
            {"address": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7", "label": "token"},
        ],
        "description": "Wrapped AVAX — ERC-20 wrapper for native AVAX",
        "category": "Token",
    },
    {
        "name": "USDC",
        "contracts": [
            {"address": "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E", "label": "token"},
        ],
        "description": "Circle's native USDC stablecoin",
        "category": "Token",
    },
    {
        "name": "USDT.e",
        "contracts": [
            {"address": "0xc7198437980c041c805A1EDcbA50c1Ce5db95118", "label": "token"},
        ],
        "description": "Bridged Tether USD",
        "category": "Token",
    },
    {
        "name": "BTC.b",
        "contracts": [
            {"address": "0x152b9d0FdC40C096DE345096A65E5BCd1545DBF7", "label": "token"},
        ],
        "description": "Bridged Bitcoin on Avalanche",
        "category": "Token",
    },
    {
        "name": "WETH.e",
        "contracts": [
            {"address": "0x49D5c2BdFfac6CE2BFDb6640F4F80f226bc10bAB", "label": "token"},
        ],
        "description": "Bridged Wrapped Ether",
        "category": "Token",
    },
    {
        "name": "JOE Token",
        "contracts": [
            {"address": "0x6e84a6216eA6dACC71eE8E6b0a5B7322EEbC0fDd", "label": "token"},
        ],
        "description": "Trader Joe governance token",
        "category": "Token",
        "website": "https://traderjoexyz.com",
    },
    {
        "name": "QI Token",
        "contracts": [
            {"address": "0x8729438EB15e2C8B576fCc6AeCdA6A148776C0F5", "label": "token"},
        ],
        "description": "Benqi governance token",
        "category": "Token",
        "website": "https://benqi.fi",
    },
    {
        "name": "PNG Token",
        "contracts": [
            {"address": "0x60781C2586D68229fde47564546784ab3fACA982", "label": "token"},
        ],
        "description": "Pangolin governance token",
        "category": "Token",
        "website": "https://pangolin.exchange",
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
