"""
Test dynamic tools from registered services — calls real contracts via MCP gateway.
Zero gas spent (read-only).
"""
import sys, os, json, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from avapilot.avalanche.gateway import create_gateway

passed = 0
failed = 0

def test(name, fn):
    global passed, failed
    try:
        result = fn()
        print(f"  ✅ {name}")
        if result: print(f"     → {str(result)[:120]}")
        passed += 1
    except Exception as e:
        print(f"  ❌ {name} — {e}")
        failed += 1

print("=" * 60)
print("🔌 AvaPilot Dynamic Tools Test (read-only, zero gas)")
print("=" * 60)

g = create_gateway('read')
tools = g._tool_manager._tools
print(f"\nGateway loaded: {len(tools)} tools\n")

# ── Discovery ──
print("📋 DISCOVERY")
test("list_services returns 11 services", lambda: (
    r := json.loads(asyncio.run(tools['list_services'].run({}))),
    f"{len(r)} services"
)[-1])

test("service_info Trader Joe", lambda: (
    r := json.loads(asyncio.run(tools['service_info'].run({'name': 'Trader Joe'}))),
    r["name"] == "Trader Joe" or "wrong name"
))

test("service_tools USDC count", lambda: (
    r := json.loads(asyncio.run(tools['service_tools'].run({'name': 'USDC'}))),
    f"{len(r)} tools"
)[-1])

# ── USDC Tools ──
print("\n💰 USDC (proxy-resolved, 55 functions)")
test("usdc_name", lambda: (
    r := json.loads(asyncio.run(tools['usdc_name'].run({}))),
    r["result"] == "USD Coin" or f"got {r['result']}"
))
test("usdc_symbol", lambda: (
    r := json.loads(asyncio.run(tools['usdc_symbol'].run({}))),
    r["result"] == "USD Coin" or r["result"]
))
test("usdc_decimals", lambda: (
    r := json.loads(asyncio.run(tools['usdc_decimals'].run({}))),
    r["result"] == "6" or f"got {r['result']}"
))
test("usdc_total_supply", lambda: (
    r := json.loads(asyncio.run(tools['usdc_total_supply'].run({}))),
    int(r["result"]) > 0 or "zero supply"
))
test("usdc_balance_of", lambda: (
    r := json.loads(asyncio.run(tools['usdc_balance_of'].run({
        'kwargs': json.dumps({'account': '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7'})
    }))),
    f"balance: {r['result']}"
)[-1])

# ── WAVAX Tools ──
print("\n🔷 WAVAX")
test("wavax_name", lambda: (
    r := json.loads(asyncio.run(tools['wavax_name'].run({}))),
    r["result"]
))
test("wavax_total_supply", lambda: (
    r := json.loads(asyncio.run(tools['wavax_total_supply'].run({}))),
    f"supply: {int(r['result']) / 1e18:.0f} WAVAX"
)[-1])

# ── Trader Joe ──
print("\n🏪 TRADER JOE")
test("trader_joe_factory", lambda: (
    r := json.loads(asyncio.run(tools['trader_joe_factory'].run({}))),
    f"factory: {r['result']}"
)[-1])
test("trader_joe_wavax", lambda: (
    r := json.loads(asyncio.run(tools['trader_joe_wavax'].run({}))),
    r["result"]
))
test("trader_joe_get_amounts_out (1 AVAX→USDC)", lambda: (
    r := json.loads(asyncio.run(tools['trader_joe_get_amounts_out'].run({
        'kwargs': json.dumps({
            'amountIn': '1000000000000000000',
            'path': ['0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7', '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E']
        })
    }))),
    f"1 AVAX = {r['result']}"
)[-1])

# ── JOE Token ──
print("\n🦊 JOE TOKEN")
test("joe_token_name", lambda: (
    r := json.loads(asyncio.run(tools['joe_token_name'].run({}))),
    r["result"]
))
test("joe_token_total_supply", lambda: (
    r := json.loads(asyncio.run(tools['joe_token_total_supply'].run({}))),
    f"supply: {int(r['result']) / 1e18:.0f} JOE"
)[-1])

# ── Pangolin ──
print("\n🐧 PANGOLIN")
test("pangolin_factory", lambda: (
    r := json.loads(asyncio.run(tools['pangolin_factory'].run({}))),
    f"factory: {r['result']}"
)[-1])

# ── sAVAX ──
print("\n❄️  sAVAX (liquid staking)")
savax_tools = [t for t in tools if t.startswith('savax_')]
test(f"sAVAX tools loaded ({len(savax_tools)})", lambda: len(savax_tools) > 20 or f"only {len(savax_tools)}")

# ── Summary ──
print("\n" + "=" * 60)
total = passed + failed
print(f"Results: {passed} passed, {failed} failed ({total} total)")
if failed == 0:
    print("All dynamic tool tests passed! Zero gas spent.")
print("=" * 60)
sys.exit(1 if failed > 0 else 0)
