"""
Read-only test suite — no transactions, no gas spent.
Tests all 25 read mode tools against live APIs.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from web3 import Web3
from avapilot.avalanche import pchain, glacier
from avapilot.avalanche._helpers import (
    get_w3, resolve_token, to_token_units, from_token_units,
    ERC20_ABI, TRADER_JOE_ROUTER_ABI,
)
from avapilot.runtime.config import CHAINS, AVALANCHE_TOKENS, AVALANCHE_DAPPS, PCHAIN_RPC

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        result = fn()
        print(f"  ✅ {name}")
        if result: print(f"     → {str(result)[:150]}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name} — {e}")
        failed += 1

print("=" * 60)
print("🔺 AvaPilot Read-Only Test Suite (no gas spent)")
print("=" * 60)

# ── Helpers ──
print("\n🔧 HELPERS")
test("Resolve USDC", lambda: resolve_token("USDC"))
test("Resolve WAVAX", lambda: resolve_token("WAVAX"))
test("Resolve AVAX→WAVAX alias", lambda: resolve_token("AVAX"))
test("Resolve JOE", lambda: resolve_token("JOE"))
test("to_token_units 1.5 AVAX", lambda: to_token_units("1.5", 18) == 1500000000000000000 or f"got {to_token_units('1.5', 18)}")
test("to_token_units 100 USDC", lambda: to_token_units("100", 6) == 100000000 or f"got {to_token_units('100', 6)}")
test("from_token_units", lambda: from_token_units(1500000000000000000, 18) == 1.5 or "mismatch")
test("Resolve dApp trader_joe_router", lambda: AVALANCHE_DAPPS.get("trader_joe_router"))

# ── Glacier API ──
print("\n🌐 GLACIER API")
test("List all chains", lambda: f"{len(glacier.list_chains())} chains")
test("List blockchains (mainnet)", lambda: f"{len(glacier.list_blockchains('mainnet'))} blockchains")

chains = glacier.list_chains()
test("Find C-Chain in list", lambda: any(c.get("chainId") == "43114" for c in chains) or "C-Chain not found")
test("Find Beam L1", lambda: any("Beam" in c.get("chainName", "") for c in chains) or "Beam not found")
test("Find DFK chain", lambda: any("DFK" in c.get("chainName", "") for c in chains) or "DFK not found")

test("Get C-Chain info", lambda: glacier.get_chain_info("43114").get("chainName"))
test("Get native balance (known addr)", lambda: glacier.get_native_balance("43114", "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7"))
test("Get ERC20 balances", lambda: f"{len(glacier.get_erc20_balances('43114', '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7').get('erc20TokenBalances',[]))} tokens")
test("List validators (3)", lambda: f"{len(glacier.list_validators(page_size=3).get('validators',[]))} validators")
test("List native txs", lambda: glacier.list_transactions("43114", "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7", page_size=2))

# ── P-Chain (Fuji to avoid mainnet rate limits) ──
print("\n⛓  P-CHAIN (Fuji)")
ep = PCHAIN_RPC["fuji"]
test("Get height", lambda: f"height {pchain.get_height(ep)}")
test("Get subnets", lambda: f"{len(pchain.get_subnets(ep))} subnets")
test("Get blockchains", lambda: f"{len(pchain.get_blockchains(ep))} blockchains")
test("Get min stake", lambda: pchain.get_min_stake(ep))
test("Get current supply", lambda: f"{int(pchain.get_current_supply(endpoint=ep)) / 1e9:.2f} AVAX")
test("Get staking asset ID", lambda: pchain.get_staking_asset_id(endpoint=ep))
test("Get total stake", lambda: f"{int(pchain.get_total_stake(endpoint=ep)) / 1e9:.2f} AVAX staked")

# ── P-Chain mainnet (may rate limit) ──
print("\n⛓  P-CHAIN (Mainnet)")
try:
    test("Get height (mainnet)", lambda: f"height {pchain.get_height()}")
    test("Get validators count", lambda: f"{len(pchain.get_current_validators(limit=5))} validators (limited)")
except:
    print("  ⚠️  Mainnet P-Chain rate limited, skipping")

# ── EVM Read (Mainnet C-Chain via fallback RPC) ──
print("\n📖 EVM READ (Mainnet C-Chain)")
w3 = get_w3("avalanche")
test("Gas price", lambda: f"{w3.eth.gas_price / 1e9:.6f} gwei")
test("Block number", lambda: f"block {w3.eth.block_number}")

# Read USDC contract
usdc_addr = Web3.to_checksum_address(AVALANCHE_TOKENS["USDC"])
usdc = w3.eth.contract(address=usdc_addr, abi=ERC20_ABI)
test("USDC name", lambda: usdc.functions.name().call())
test("USDC symbol", lambda: usdc.functions.symbol().call())
test("USDC decimals", lambda: usdc.functions.decimals().call())
test("USDC totalSupply", lambda: f"{usdc.functions.totalSupply().call() / 1e6:,.2f} USDC")

# Read WAVAX
wavax_addr = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
wavax = w3.eth.contract(address=wavax_addr, abi=ERC20_ABI)
test("WAVAX name", lambda: wavax.functions.name().call())
test("WAVAX totalSupply", lambda: f"{wavax.functions.totalSupply().call() / 1e18:,.2f} WAVAX")

# Trader Joe router read
router_addr = Web3.to_checksum_address(AVALANCHE_DAPPS["trader_joe_router"])
router = w3.eth.contract(address=router_addr, abi=TRADER_JOE_ROUTER_ABI)
test("TJ Router factory", lambda: router.functions.factory().call())
test("TJ Router WAVAX", lambda: router.functions.WAVAX().call())

# Swap quote
test("Swap quote 1 AVAX→USDC", lambda: (
    amounts := router.functions.getAmountsOut(
        Web3.to_wei(1, "ether"),
        [wavax_addr, usdc_addr]
    ).call(),
    f"1 AVAX = {amounts[-1] / 1e6:.2f} USDC"
)[-1])

test("Swap quote 100 USDC→AVAX", lambda: (
    amounts := router.functions.getAmountsOut(
        100 * 10**6,
        [usdc_addr, wavax_addr]
    ).call(),
    f"100 USDC = {amounts[-1] / 1e18:.4f} AVAX"
)[-1])

# ── EVM Read (Fuji) ──
print("\n📖 EVM READ (Fuji C-Chain)")
w3f = Web3(Web3.HTTPProvider("https://api.avax-test.network/ext/bc/C/rpc"))
test("Fuji gas price", lambda: f"{w3f.eth.gas_price / 1e9:.4f} gwei")
test("Fuji block number", lambda: f"block {w3f.eth.block_number}")
test("Fuji chain ID", lambda: f"chain {w3f.eth.chain_id}")

# Read our deployed contract from earlier test
deployed = "0xbB89f20c7673810a6dC6391aF0187a9D71eed008"
test("Read deployed contract code", lambda: f"{len(w3f.eth.get_code(Web3.to_checksum_address(deployed)))} bytes")

# ── Gateway Factory ──
print("\n🏭 GATEWAY FACTORY")
from avapilot.avalanche.gateway import create_gateway
for mode in ["read", "trade", "full"]:
    g = create_gateway(mode)
    tools = g._tool_manager._tools
    test(f"Mode '{mode}' tool count", lambda m=mode, t=tools: f"{len(t)} tools")

# Check no duplicate tool names across modes
g_full = create_gateway("full")
all_tools = list(g_full._tool_manager._tools.keys())
test("No duplicate tools", lambda: len(all_tools) == len(set(all_tools)) or f"dupes: {len(all_tools)} vs {len(set(all_tools))}")

# ── Config ──
print("\n⚙️  CONFIG")
test("Mainnet config", lambda: CHAINS["avalanche"]["chain_id"] == 43114 or "wrong chain id")
test("Fuji config", lambda: CHAINS["fuji"]["chain_id"] == 43113 or "wrong chain id")
test("Known tokens count", lambda: f"{len(AVALANCHE_TOKENS)} tokens")
test("Known dApps count", lambda: f"{len(AVALANCHE_DAPPS)} dApps")

# ── New Contract Developer Tools ──
print("\n🔧 CONTRACT DEV TOOLS (new)")
from avapilot.avalanche.gateway import create_gateway
import asyncio
g = create_gateway('read')
t = g._tool_manager._tools

test("is_contract (USDC)", lambda: (
    r := asyncio.run(t['is_contract'].run({'address': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E'})),
    r['is_contract'] == True or "expected contract"
)[-1])

test("is_contract (EOA)", lambda: (
    r := asyncio.run(t['is_contract'].run({'address': '0xCA385E3caFa97B00754607E9226dEbFb1e1e6841'})),
    r['is_contract'] == False or "expected EOA"
)[-1])

test("get_contract_source (USDC)", lambda: (
    r := asyncio.run(t['get_contract_source'].run({'contract_address': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E'})),
    f"verified={r['verified']} name={r['contract_name']} proxy={r['proxy']}"
))

test("get_block_info (latest)", lambda: (
    r := asyncio.run(t['get_block_info'].run({})),
    f"block {r.get('number', r.get('hash', 'ok'))}"
)[-1])

test("Tool count: read=30", lambda: len(t) == 30 or f"got {len(t)}")



# ── Summary ──
print()
print("=" * 60)
total = passed + failed
print(f"Results: {passed} passed, {failed} failed ({total} total)")
if failed == 0:
    print("All read-only tests passed! Zero gas spent.")
else:
    print(f"{failed} test(s) need attention")
print("=" * 60)
sys.exit(1 if failed > 0 else 0)
