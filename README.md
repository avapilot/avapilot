# AvaPilot

**The MCP gateway for Avalanche.**

Connect your AI agent once. It discovers every protocol, reads any contract, executes any trade. New services added via GitHub PR.

```
Protocol opens PR → AvaPilot merges → Every AI agent discovers it
```

*Open source · MIT License · Supported by Avalanche Foundation*

---

## Quick start

```bash
git clone https://github.com/avapilot/avapilot.git
cd avapilot
uv pip install -e .              # Install (or: pip install -e .)
avapilot seed                    # Load known Avalanche dApps
avapilot gateway --mode read     # Start MCP gateway
```

Connect to your AI:

```json
// Claude Desktop (claude_desktop_config.json)
{
  "mcpServers": {
    "avapilot": {
      "command": "avapilot",
      "args": ["gateway", "--mode", "read"]
    }
  }
}
```

```yaml
# OpenClaw (~/.openclaw/config.yaml)
mcp:
  servers:
    avapilot:
      command: avapilot
      args: [gateway, --mode, trade]
```

Then ask:

- *"What DeFi protocols are available on Avalanche?"*
- *"Get me a swap quote for 10 AVAX to USDC"*
- *"What's the sAVAX staking APR?"*
- *"Swap 1 AVAX for USDC on Trader Joe"*

## Architecture

```
AI Agent (Claude, GPT, etc.)
  │
  │  "What can I do on Avalanche?"
  │  search_services() → 12 protocols
  │  service_functions("Trader Joe") → 24 functions
  │  call_service("Trader Joe", "getAmountsOut", {...})
  │  → "1 AVAX = 9.50 USDC"
  │
  ↕  MCP Protocol (stdio)
  │
AvaPilot Gateway
  │  45 built-in tools (network, gas, contracts, wallet)
  │  + lazy discovery (search → inspect → call)
  │  + 12 registered services (374 contract functions)
  │  + proxy-aware ABI resolution
  │  + local key signing
  │
  ↕  JSON-RPC
  │
Avalanche (C-Chain, P-Chain, 118+ L1s)
```

**Lazy discovery** — The AI gets 45 clean tools, not 500. It searches services on-demand and calls specific functions. Scales to thousands of protocols without tool bloat.

## Gateway modes

| Mode | Tools | Wallet | Use case |
|------|-------|--------|----------|
| `read` | 34 | No | Query, research, explore |
| `trade` | 43 | Yes | Send, swap, approve |
| `full` | 45 | Yes | Deploy contracts |

```bash
export AVAPILOT_PRIVATE_KEY=0x...
avapilot gateway --mode trade
```

Keys never leave your machine.

## Registered services

| Service | Category | Functions | Notes |
|---------|----------|-----------|-------|
| sAVAX | DeFi | 70 | Benqi liquid staking |
| ggAVAX | DeFi | 65 | GoGoPool liquid staking |
| Stargate USDC | DeFi | 61 | Cross-chain pool |
| USDC | Token | 55 | Proxy-resolved |
| JOE Token | Token | 26 | Governance |
| Trader Joe | DeFi | 24 | DEX router |
| Pangolin | DeFi | 24 | Community DEX |
| USDT.e | Token | 22 | Bridged Tether |
| Trader Joe Factory | DeFi | 11 | LP pair factory |
| WAVAX | Token | 11 | Wrapped AVAX |
| Aave V3 | DeFi | 5 | Lending |

**Want your protocol here?** Open a PR adding it to `avapilot/registry/seed.py`.

## For protocols

```bash
# See what AvaPilot detects from your contract
avapilot scan 0xYourContract

# Add to seed.py and open a PR
# Every user who updates gets your protocol
```

Auto-fetches ABI. Detects proxies. Zero coding.

## CLI

```bash
avapilot gateway [--mode read|trade|full]   # Start MCP gateway
avapilot scan 0xAddress                      # Analyze any contract
avapilot register "Name" 0xAddr              # Register a service
avapilot services                            # List registered services
avapilot inspect "Name"                      # Inspect a service
avapilot seed                                # Load known dApps
avapilot info                                # Network stats
avapilot api [--port 8080]                   # REST API server
```

## Tests

```bash
python tests/test_read_only.py       # 56 tests, zero gas
python tests/test_lazy_discovery.py  # 28 tests, lazy discovery
python tests/test_fuji.py           # 18 tests, real txs on Fuji
```

102 tests. 0 failures.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
