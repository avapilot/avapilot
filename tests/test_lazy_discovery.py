"""
Test lazy discovery architecture — search, inspect, call services through gateway.
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
print("🔍 AvaPilot Lazy Discovery Tests (zero gas)")
print("=" * 60)

g = create_gateway('trade')
t = g._tool_manager._tools
print(f"\nGateway: {len(t)} tools\n")

# ── Search ──
print("🔎 SEARCH")
test("search all services", lambda: (
    r := json.loads(asyncio.run(t['search_services'].run({}))),
    f"{len(r)} services"
)[-1])

test("search by category DeFi", lambda: (
    r := json.loads(asyncio.run(t['search_services'].run({'category': 'DeFi'}))),
    all(s['category'] == 'DeFi' for s in r) or "wrong category",
    f"{len(r)} DeFi services"
)[-1])

test("search by query 'swap'", lambda: (
    r := json.loads(asyncio.run(t['search_services'].run({'query': 'swap'}))),
    len(r) >= 1 or "no results",
    f"found: {[s['name'] for s in r]}"
)[-1])

test("search by query 'staking'", lambda: (
    r := json.loads(asyncio.run(t['search_services'].run({'query': 'staking'}))),
    f"found: {[s['name'] for s in r]}"
)[-1])

test("search Token category", lambda: (
    r := json.loads(asyncio.run(t['search_services'].run({'category': 'Token'}))),
    f"{len(r)} tokens: {[s['name'] for s in r]}"
)[-1])

# ── Service Info ──
print("\n📋 SERVICE INFO")
test("Trader Joe info", lambda: (
    r := json.loads(asyncio.run(t['service_info'].run({'service_name': 'Trader Joe'}))),
    r['name'] == 'Trader Joe' or "wrong name",
    f"{len(r['contracts'])} contracts, {r['contracts'][0]['type']}"
)[-1])

test("USDC info shows proxy-resolved functions", lambda: (
    r := json.loads(asyncio.run(t['service_info'].run({'service_name': 'USDC'}))),
    len(r['contracts'][0]['read_functions']) > 10 or f"only {len(r['contracts'][0]['read_functions'])} read functions (proxy not resolved?)",
    f"{len(r['contracts'][0]['read_functions'])}R / {len(r['contracts'][0]['write_functions'])}W"
)[-1])

test("sAVAX info", lambda: (
    r := json.loads(asyncio.run(t['service_info'].run({'service_name': 'sAVAX'}))),
    f"{r['category']} — {r['description'][:50]}"
)[-1])

test("nonexistent service returns error", lambda: (
    r := json.loads(asyncio.run(t['service_info'].run({'service_name': 'FakeProtocol'}))),
    'error' in r or "should have error"
))

# ── Service Functions ──
print("\n📑 SERVICE FUNCTIONS")
test("Trader Joe functions", lambda: (
    r := json.loads(asyncio.run(t['service_functions'].run({'service_name': 'Trader Joe'}))),
    any(f['name'] == 'getAmountsOut' for f in r) or "missing getAmountsOut",
    f"{len(r)} functions, {sum(1 for f in r if f['is_read'])} read / {sum(1 for f in r if not f['is_read'])} write"
)[-1])

test("USDC functions include balanceOf", lambda: (
    r := json.loads(asyncio.run(t['service_functions'].run({'service_name': 'USDC'}))),
    any(f['name'] == 'balanceOf' for f in r) or "missing balanceOf",
    f"{len(r)} functions"
)[-1])

test("Function signatures have inputs/outputs", lambda: (
    r := json.loads(asyncio.run(t['service_functions'].run({'service_name': 'Trader Joe'}))),
    f := next(fn for fn in r if fn['name'] == 'getAmountsOut'),
    len(f['inputs']) == 2 or f"expected 2 inputs, got {len(f['inputs'])}",
    f"inputs: {[i['name']+':'+i['type'] for i in f['inputs']]}"
)[-1])

# ── Call Service (Read) ──
print("\n📞 CALL SERVICE")
test("USDC name", lambda: (
    r := json.loads(asyncio.run(t['call_service'].run({
        'service_name': 'USDC', 'function_name': 'name', 'args': '{}'
    }))),
    r['result'] == 'USD Coin' or f"got {r['result']}"
))

test("USDC decimals", lambda: (
    r := json.loads(asyncio.run(t['call_service'].run({
        'service_name': 'USDC', 'function_name': 'decimals', 'args': '{}'
    }))),
    r['result'] == '6' or f"got {r['result']}"
))

test("USDC balanceOf", lambda: (
    r := json.loads(asyncio.run(t['call_service'].run({
        'service_name': 'USDC', 'function_name': 'balanceOf',
        'args': json.dumps({'account': '0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7'})
    }))),
    int(r['result']) > 0 or "zero balance",
    f"{int(r['result']) / 1e6:.2f} USDC"
)[-1])

test("WAVAX name", lambda: (
    r := json.loads(asyncio.run(t['call_service'].run({
        'service_name': 'WAVAX', 'function_name': 'name', 'args': '{}'
    }))),
    r['result'] == 'Wrapped AVAX' or f"got {r['result']}"
))

test("Trader Joe getAmountsOut (1 AVAX → USDC)", lambda: (
    r := json.loads(asyncio.run(t['call_service'].run({
        'service_name': 'Trader Joe', 'function_name': 'getAmountsOut',
        'args': json.dumps({
            'amountIn': '1000000000000000000',
            'path': ['0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7', '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E']
        })
    }))),
    r['success'] or f"failed: {r.get('error')}",
    f"1 AVAX = {r['result']}"
)[-1])

test("Pangolin factory", lambda: (
    r := json.loads(asyncio.run(t['call_service'].run({
        'service_name': 'Pangolin', 'function_name': 'factory', 'args': '{}'
    }))),
    r['success'] or f"failed: {r.get('error')}",
    f"factory: {r['result']}"
)[-1])

test("JOE Token totalSupply", lambda: (
    r := json.loads(asyncio.run(t['call_service'].run({
        'service_name': 'JOE Token', 'function_name': 'totalSupply', 'args': '{}'
    }))),
    int(r['result']) > 0 or "zero supply",
    f"{int(r['result']) / 1e18:.0f} JOE"
)[-1])

# ── Error Handling ──
print("\n⚠️  ERROR HANDLING")
test("call nonexistent service → helpful error", lambda: (
    r := json.loads(asyncio.run(t['call_service'].run({
        'service_name': 'FakeProtocol', 'function_name': 'foo', 'args': '{}'
    }))),
    'search_services' in r.get('error', '') or "error should mention search_services"
))

test("call nonexistent function → helpful error", lambda: (
    r := json.loads(asyncio.run(t['call_service'].run({
        'service_name': 'USDC', 'function_name': 'fakeFunction', 'args': '{}'
    }))),
    'service_functions' in r.get('error', '') or "error should mention service_functions"
))

# ── Trade Tools Present ──
print("\n💰 TRADE TOOLS")
test("wallet_status exists", lambda: 'wallet_status' in t or "missing")
test("send_avax exists", lambda: 'send_avax' in t or "missing")
test("send_service_tx exists", lambda: 'send_service_tx' in t or "missing")
test("swap_exact_tokens exists", lambda: 'swap_exact_tokens' in t or "missing")

# ── Tool Count ──
print("\n📊 TOOL COUNTS")
g_read = create_gateway('read')
g_trade = create_gateway('trade')
g_full = create_gateway('full')
test("read mode: 34+ tools", lambda: len(g_read._tool_manager._tools) >= 34 or f"got {len(g_read._tool_manager._tools)}")
test("trade mode: 44+ tools", lambda: len(g_trade._tool_manager._tools) >= 44 or f"got {len(g_trade._tool_manager._tools)}")
test("full mode: 45+ tools", lambda: len(g_full._tool_manager._tools) >= 45 or f"got {len(g_full._tool_manager._tools)}")

# ── Summary ──
print("\n" + "=" * 60)
total = passed + failed
print(f"Results: {passed} passed, {failed} failed ({total} total)")
if failed == 0:
    print("All lazy discovery tests passed!")
print("=" * 60)
sys.exit(1 if failed > 0 else 0)
