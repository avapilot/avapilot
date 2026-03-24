# AvaPilot

**The MCP gateway for the Avalanche ecosystem.**

Protocols register their smart contracts. Users connect their AI agent once. The AI can use everything.

One gateway. All of Avalanche.

*Open source · Supported by Avalanche Foundation*

---

## What it does

AvaPilot turns any Avalanche smart contract into MCP tools that AI agents can use. No coding required.

```
Protocol registers contract → AvaPilot auto-generates tools → Every AI agent gets access
```

**Right now:** 11 services, 363+ dynamic tools, 40 built-in tools, 118 L1 chains indexed.

## Quick start

```bash
git clone https://github.com/avapilot/avapilot.git
cd avapilot
pip install -e .

avapilot seed                    # Load known Avalanche dApps
avapilot gateway --mode read     # Start the gateway
```

Add to your MCP client:

```yaml
# OpenClaw (~/.openclaw/config.yaml)
mcp:
  servers:
    avapilot:
      command: avapilot
      args: [gateway, --mode, trade]
```

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

Then ask your AI:

- *"What DeFi services are available on Avalanche?"*
- *"Swap 1 AVAX for USDC"*
- *"Show me the top validators"*
- *"What L1 chains are running?"*

## For protocols

```bash
avapilot scan 0xYourContract       # See what AvaPilot detects
avapilot register "Your Protocol" 0xYourContract --category DeFi
# Done. Every connected AI agent can now use your protocol.
```

Auto-fetches ABI. Detects proxies. Categorizes functions. Zero coding.

## Gateway modes

| Mode | Tools | Wallet | Use case |
|------|-------|--------|----------|
| `read` | All reads + discovery | No | Explore, query, research |
| `trade` | Read + send/swap/approve | Yes | DeFi, transfers |
| `full` | Trade + deploy/write | Yes | Power user |

```bash
export AVAPILOT_PRIVATE_KEY=0x...
avapilot gateway --mode trade
```

Keys never leave your machine.

## Registered services

| Service | Category | Tools |
|---------|----------|-------|
| Trader Joe | DeFi | 24 |
| Pangolin | DeFi | 24 |
| USDC | Token | 55 |
| sAVAX | DeFi | 70 |
| ggAVAX | DeFi | 65 |
| Stargate USDC | DeFi | 61 |
| JOE Token | Token | 26 |
| USDT.e | Token | 22 |
| WAVAX | Token | 11 |
| Aave V3 | DeFi | 5 |

## CLI

```bash
avapilot gateway [--mode read|trade|full]   # Start MCP gateway
avapilot scan 0xAddress                      # Analyze any contract
avapilot register "Name" 0xAddr              # Register a service
avapilot services                            # List services
avapilot inspect "Name"                      # Inspect a service
avapilot seed                                # Load known dApps
avapilot info                                # Network stats
```

## Tests

```bash
python tests/test_read_only.py       # 56 tests, zero gas
python tests/test_dynamic_tools.py   # 17 tests, dynamic tools
python tests/test_fuji.py            # 18 tests, real txs on Fuji
```

91 tests. 0 failures.

## License

MIT
