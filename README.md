# AvaPilot

Talk to Avalanche from any AI agent. One install. Every protocol.

```
"What DeFi protocols are on Avalanche?"  →  finds 12 protocols
"Swap 1 AVAX for USDC"                  →  executes on Trader Joe
"Create a new L1 blockchain"            →  creates a subnet on Fuji
```

---

## Install

You need Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/avapilot/avapilot.git
cd avapilot
uv pip install -e .
avapilot seed
```

That's it. AvaPilot is installed.

**Optional:** For L1 creation and staking, also install [platform-cli](https://github.com/ava-labs/platform-cli):
```bash
go install github.com/ava-labs/platform-cli@latest
```

## Connect to your AI

Pick one. Copy-paste the config.

**Claude Desktop** — open `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "avapilot": {
      "command": "avapilot",
      "args": ["gateway", "--mode", "trade", "--chain", "fuji"]
    }
  }
}
```

**OpenClaw** — add to your config:
```yaml
mcp:
  servers:
    avapilot:
      command: avapilot
      args: [gateway, --mode, trade, --chain, fuji]
```

**Cursor / Windsurf / any MCP client** — same pattern. Command is `avapilot`, args are `gateway --mode trade --chain fuji`.

> **Start with `--chain fuji`** (testnet). Switch to `--chain avalanche` when you're ready for real money. Get free testnet AVAX at [faucet.avax.network](https://faucet.avax.network).

Restart your AI client. Done.

## Set up a wallet

Skip this if you only want to read data (`--mode read`).

```bash
export AVAPILOT_PRIVATE_KEY=0xYourPrivateKeyHere
```

Put this in your shell profile (`~/.zshrc` or `~/.bashrc`) so it persists.

> ⚠️ **Your key never leaves your machine.** AvaPilot signs transactions locally. The key is never sent anywhere. Verify it yourself — we're open source.

## What you can do

### Read (no wallet needed)
- "What protocols are available on Avalanche?"
- "What's the gas price right now?"
- "Show me the top validators"
- "What's the USDC total supply?"
- "How many L1 chains are running?"

### Trade (needs wallet)
- "Send 1 AVAX to 0x..."
- "Wrap 5 AVAX to WAVAX"
- "Swap 10 AVAX for USDC on Trader Joe"
- "What's my wallet balance?"

### L1 & Staking (needs wallet + platform-cli)
- "Transfer 2 AVAX from C-Chain to P-Chain"
- "Create a new subnet"
- "Delegate 100 AVAX to a validator"

## Modes

| Mode | What it can do | Needs wallet? |
|------|---------------|---------------|
| `read` | Query anything. Can't spend money. | No |
| `trade` | Read + send, swap, wrap, stake, create L1s. | Yes |
| `full` | Trade + deploy smart contracts. | Yes |

```bash
avapilot gateway --mode read --chain avalanche    # Safe. Read-only. Mainnet.
avapilot gateway --mode trade --chain fuji        # Testnet trading.
avapilot gateway --mode trade --chain avalanche   # Real money. Be careful.
```

## Add a protocol

Any Avalanche smart contract can be added. Two ways:

**Quick (local only):**
```bash
avapilot register "GMX" 0x62edc0692BD897D2295872a9FFCac5425011c661 --category DeFi
```
Your AI can use it immediately.

**Permanent (for everyone):**

Add it to `avapilot/registry/seed.py` and open a PR. Once merged, every AvaPilot user gets it.

AvaPilot auto-fetches the ABI, detects proxy contracts, and categorizes every function. You just provide the address.

## How it works

Your AI gets ~60 tools. Most are built-in (gas prices, validators, balances). Five are "discovery" tools:

1. **search_services** — find protocols by name or category
2. **service_info** — get details about a protocol
3. **service_functions** — see every callable function
4. **call_service** — call a read function on-chain
5. **send_service_tx** — execute a write transaction

The AI searches first, then calls. This means AvaPilot can support thousands of protocols without overwhelming your AI with thousands of tools.

## CLI reference

```bash
avapilot seed                         # Load known protocols (run once after install)
avapilot gateway --mode trade         # Start the MCP gateway
avapilot gateway --chain fuji         # Use testnet
avapilot services                     # List what's registered
avapilot inspect "Trader Joe"         # See a protocol's functions
avapilot scan 0xAnyContract           # Analyze any contract
avapilot register "Name" 0xAddr       # Register a new protocol
avapilot info                         # Avalanche network stats
```

## Troubleshooting

**"avapilot: command not found"**
```bash
uv pip install -e .    # Run this from the avapilot directory
```

**"No wallet configured"**
```bash
export AVAPILOT_PRIVATE_KEY=0xYourKey
```

**"Service not found"**
```bash
avapilot seed          # Load the default protocols
```

**Transactions failing on Fuji?**
Get test AVAX: [faucet.avax.network](https://faucet.avax.network)

**platform-cli not found?**
```bash
go install github.com/ava-labs/platform-cli@latest
export PATH=$PATH:~/go/bin
```

## Registered protocols

| Protocol | Type | Functions |
|----------|------|-----------|
| sAVAX | DeFi | 70 |
| ggAVAX | DeFi | 65 |
| Stargate USDC | DeFi | 61 |
| USDC | Token | 55 |
| JOE Token | Token | 26 |
| Trader Joe | DeFi | 24 |
| Pangolin | DeFi | 24 |
| USDT.e | Token | 22 |
| Trader Joe Factory | DeFi | 11 |
| WAVAX | Token | 11 |
| Aave V3 | DeFi | 5 |

[Add yours →](https://github.com/avapilot/avapilot/blob/main/avapilot/registry/seed.py)

## License

MIT — do whatever you want with it.
