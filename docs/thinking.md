# AvaPilot — Thinking Doc

_Rex's research & strategy notes. Read this when you wake up, Jianian._
_Last updated: 2026-03-24 00:00 GMT_

---

## Where We Are (Status as of tonight)

### What's Built & Working
```
avapilot/
├── avalanche/
│   ├── gateway.py          ← mode-based MCP server factory (read/trade/full)
│   ├── tools_read.py       ← 30 built-in read tools
│   ├── tools_trade.py      ← 8 trade tools (send, swap, wrap, approve)
│   ├── tools_full.py       ← 2 power tools (deploy, write_contract)
│   ├── _helpers.py         ← shared ABIs, Web3, token resolution
│   ├── wallet.py           ← private key from .env, auto-load
│   ├── pchain.py           ← P-Chain RPC (validators, subnets, staking)
│   └── glacier.py          ← Glacier Data API (chains, balances, NFTs)
├── registry/
│   ├── store.py            ← SQLite service registry
│   ├── models.py           ← Service, ServiceContract dataclasses
│   └── seed.py             ← Pre-loaded: Trader Joe, Benqi, Aave V3, USDC, WAVAX
├── generator/              ← ABI→MCP server generator (standalone)
├── runtime/                ← Chain configs, EVM helpers
└── marketplace/            ← Old web UI skeleton (partially obsolete)
```

### Test Results
- **Fuji testnet:** 18/18 ✅ (send AVAX, wrap/unwrap, deploy contract — real txs)
- **Read-only suite:** 56/56 ✅ (Glacier, P-Chain, EVM, helpers, gateway factory)
- **Dynamic gateway with registry:** ✅ 48 tools in read mode (30 built-in + 15 dynamic + 3 discovery)

### Git Log (agent-infra branch)
```
6b0adf1 feat: service registry platform
9b8cfee feat: contract dev tools (events, source, is_contract, block_info, decode_tx)
8ae29ca test: comprehensive read-only suite — 56/56
85317ef test: full Fuji testnet suite — 18/18
636a024 feat: auto-load .env for wallet config
2c51609 refactor: split gateway into read/trade/full modes
0475e97 fix: RPC fallback, Decimal precision, AVAX alias
37f9c33 feat: full Avalanche MCP Gateway — wallet, swaps, transfers, contracts, gas
b3fc938 feat: Avalanche-native L1 features — P-Chain, Glacier, built-in MCP tools
```

---

## The Big Idea

**AvaPilot = The MCP gateway for the Avalanche ecosystem.**

Not a tool. Not a library. An **infrastructure layer.**

```
Protocol registers contract → AvaPilot auto-generates MCP tools → Every AI agent gets access
```

One connection. Entire ecosystem. Open source. Backed by Avalanche Foundation.

---

## Competitive Landscape (What Exists)

### MCP Tool Registries / Marketplaces
- **Smithery.ai** — MCP server marketplace, but general-purpose (not blockchain-specific)
- **mcp.run** — another general MCP hub
- **glama.ai/mcp** — MCP server directory
- None of these are chain-specific. None auto-generate from ABIs. None have a registry where protocols self-serve.

### Blockchain AI Agent Tools
- **Goat SDK** — multi-chain AI agent framework (competitor, but SDK not gateway)
- **Brian.so** — natural language blockchain transactions (different angle — they process language, we expose tools)
- **Olas** — autonomous agent framework (different layer — agent orchestration, not tool provisioning)
- **Bankless MCP servers** — one-off MCP servers for specific chains (Ethereum, etc.)

### Gap We Fill
Nobody is doing: **"protocol registers once → all AI agents get access → on Avalanche."**

This is our wedge. We're not competing with Goat SDK on multi-chain. We're going deep on Avalanche.

---

## Architecture Decision: Discovery Model

### Option A: Everything Loaded (Current)
Gateway starts → loads ALL registered service tools → AI has everything.

**Pros:** Simple, fast, no extra calls
**Cons:** 500 services × 20 tools = 10,000 tools loaded. AI drowns in options.

### Option B: Lazy Discovery (Recommended) ✅
Gateway starts with built-in tools + 3 discovery tools. AI searches registry, gets tools on-demand.

```
User: "Swap my AVAX for USDC"
AI calls: search_services("swap tokens") → finds Trader Joe
AI calls: use_service("Trader Joe", "getAmountsOut", [amount, path]) → gets quote
AI calls: use_service("Trader Joe", "swapExactTokensForTokens", [...]) → executes
```

**Pros:** Scales to thousands of services. AI picks the right one contextually.
**Cons:** Extra round-trip for discovery. Need good search/matching.

### Option C: Hybrid (Best of Both)
- Core services always loaded (top 10-20 by usage)
- Everything else via discovery
- AI can "pin" services it uses frequently

**Decision: Start with A (current), plan migration to C.**
With 5 seeded services, A works fine. Build C when we hit 50+ services.

---

## What the Registry Should Look Like (Product Thinking)

### For Protocols (Supply Side)
```bash
# Dead simple registration
avapilot register "My Protocol" 0xContractAddress

# That's it. AvaPilot:
# 1. Fetches ABI from Snowtrace
# 2. Identifies contract type (DEX, lending, NFT, token, etc.)
# 3. Categorizes functions (read vs write)
# 4. Generates tool names and descriptions
# 5. Stores in registry
# 6. Available to ALL connected AI agents immediately
```

### For Users (Demand Side)
```yaml
# Add to OpenClaw/Claude Desktop config — one time
mcp:
  servers:
    avapilot:
      command: avapilot
      args: [gateway, --mode, trade]
```

Then just talk naturally:
- "What DeFi services are available on Avalanche?"
- "Swap 1 AVAX for USDC using the best rate"
- "Check my staking rewards"
- "Deploy a simple ERC-20 token"

### For the Ecosystem
- Open source = anyone can verify, contribute, fork
- Foundation backing = credibility, distribution, support
- Protocol-agnostic within Avalanche = everyone benefits

---

## What Needs to Happen Before Public Launch

### Must Have (P0)
- [ ] **LICENSE file** — MIT (most permissive, best for ecosystem adoption)
- [ ] **Clean README** — what it is, how to use, Foundation credit
- [ ] **CONTRIBUTING.md** — how to add services, contribute code
- [ ] **Remove old marketplace/** — it's been superseded by registry/
- [ ] **Verify .env / secrets never in git history** — `git log --all -p | grep PRIVATE_KEY`
- [ ] **gateway-ui deployed** — GitHub Pages on avapilot.github.io or custom domain

### Should Have (P1)
- [ ] **`pip install avapilot`** — publish to PyPI for easy install
- [ ] **CI/CD** — GitHub Actions: run test suite on PR
- [ ] **Rate limiting awareness** — graceful handling of Snowtrace/RPC rate limits
- [ ] **Better error messages** — user-friendly errors for common issues
- [ ] **Proxy contract handling** — auto-fetch implementation ABI for proxies (USDC only shows 5 tools because it's a proxy)

### Nice to Have (P2)
- [ ] **Web registration portal** — register via web form, not just CLI
- [ ] **Usage analytics** — which tools are called most (opt-in, privacy-respecting)
- [ ] **Multi-chain L1 support** — register contracts on any Avalanche L1, not just C-Chain
- [ ] **Service verification** — prove you own the contract (signature challenge)
- [ ] **Tool quality scores** — rate tools based on ABI completeness, documentation

---

## Open Questions (For You to Think About)

### 1. Naming
"AvaPilot" is good but... is it a pilot (copilot?) or a platform?
- **AvaPilot** — implies assistant/copilot
- **AvaHub** — implies platform/marketplace (taken?)
- **AvaGate** — implies gateway (which it literally is)
- Keep AvaPilot? The name has momentum.

### 2. Where Does This Live?
- `github.com/avapilot/avapilot` (current, org exists)
- `github.com/ava-labs/avapilot` (under Ava Labs — more credibility, but you lose control)
- Keep it under your org. Foundation can endorse without owning.

### 3. First Users
Who registers first? You should have 10+ services at launch.
- **Auto-seed candidates:** Trader Joe, Pangolin, Benqi, Aave V3, GMX, Platypus, USDC, USDT, WAVAX, BTC.b, JOE
- **Reach out candidates:** Beam (gaming L1), DFK (gaming), GoGoPool (liquid staking)
- The more services at launch, the more useful the gateway is, the more users come, the more protocols want to register. **Flywheel.**

### 4. Foundation Relationship
- Is this a grant project? Funded development?
- Can you use the Avalanche logo/branding?
- Will they promote it through their channels?
- Get clarity on this — it affects everything from README to marketing.

### 5. Proxy Contracts
USDC on Avalanche is a proxy (FiatTokenProxy). Our registry only gets 5 proxy functions, not the 30+ implementation functions. Need to:
1. Detect proxy pattern
2. Fetch implementation address
3. Merge ABIs
This is a real issue — many major contracts are proxies.

---

## Technical Debt / Known Issues

1. **Trade tools untested on Fuji via gateway** — we tested raw Web3 calls, not through the MCP tool wrappers
2. **`chain` parameter** — most trade tools hardcode "avalanche", need Fuji support for all
3. **Benqi returns 0 tools** — probably a proxy or non-standard ABI issue
4. **No pagination** in registry — fine for now, problem at 100+ services
5. **Tool name collisions** — if two services have `admin()`, they collide. Need namespacing.
6. **No tool description enrichment** — ABI function names are cryptic. Need human-readable descriptions.
7. **gateway-ui not updated** with platform/registry info

---

## Rough Roadmap

### Week 1: Ship Public
- Clean repo, add LICENSE, README, CONTRIBUTING
- Fix proxy contract ABI fetching
- Deploy gateway-ui
- Seed 10+ services
- Flip repo to public
- Post on Twitter/X, tag Avalanche

### Week 2: Distribution
- Publish to PyPI (`pip install avapilot`)
- Write tutorial: "Give Your AI Agent Access to Avalanche in 5 Minutes"
- Submit to Smithery.ai, mcp.run, glama.ai directories
- Reach out to 5 Avalanche protocols to register

### Week 3: Polish
- Web registration portal
- Better tool descriptions (use LLM to enrich ABI descriptions)
- CI/CD pipeline
- Documentation site

### Month 2: Scale
- Multi-L1 support
- Usage analytics dashboard
- Community contributions
- Foundation showcase/demo

---

## One More Thing

The real moat isn't the code. It's the **registry network effect.**

```
More protocols register → More useful for AI agents → More users → More protocols want to register
```

First mover wins. Nobody is doing this for Avalanche. Get there first, own the standard.

Ship fast. Ship public. Ship now.

— Rex 🦞
