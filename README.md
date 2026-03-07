# 🔺 AvaPilot

**Turn any Avalanche smart contract into an AI-ready MCP server in one command.**

AvaPilot generates [Model Context Protocol](https://modelcontextprotocol.io) servers from smart contract ABIs — so any AI agent (Claude, OpenClaw, GPT, etc.) can interact with any dApp on Avalanche.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/avapilot/avapilot.git
cd avapilot

# 2. Generate an MCP server from any Avalanche contract
uv run python cli.py generate 0x60aE616a2155Ee3d9A68541Ba4544862310933d4 \
  --name "Trader Joe" \
  --output ./my-trader-joe-mcp

# 3. That's it. You now have a working MCP server.
cd my-trader-joe-mcp
pip install -r requirements.txt
python server.py
```

Your AI agent can now swap tokens, check prices, and add liquidity on Trader Joe.

## What It Does

```
Your Contract Address
        ↓
   avapilot generate
        ↓
   Ready-to-run MCP Server
        ↓
   Connect to Claude / OpenClaw / Any AI Agent
```

For each contract function, AvaPilot generates:
- **Read tools** → query on-chain state (balances, prices, allowances)
- **Write tools** → build unsigned transactions (you sign with your own wallet)

No private keys. No wallet access. Just tool generation.

## Examples

### Generate from contract address
```bash
uv run python cli.py generate 0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E \
  --name "USDC" --output ./usdc-mcp
```

### Generate from known dApp name
```bash
# AvaPilot knows popular Avalanche dApps
uv run python cli.py generate trader_joe_router --output ./traderjoe-mcp
uv run python cli.py generate pangolin_router --output ./pangolin-mcp
uv run python cli.py generate benqi_comptroller --output ./benqi-mcp
uv run python cli.py generate aave_pool --output ./aave-mcp
```

### Use Fuji testnet
```bash
uv run python cli.py generate 0xYourContract --chain fuji --output ./my-mcp
```

## Connect to Claude Desktop

After generating, add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "trader-joe": {
      "command": "python",
      "args": ["/path/to/my-trader-joe-mcp/server.py"],
      "env": {
        "RPC_URL": "https://api.avax.network/ext/bc/C/rpc"
      }
    }
  }
}
```

Now ask Claude: *"What's the best route to swap 1 AVAX for USDC on Trader Joe?"*

## Connect to OpenClaw

Add AvaPilot-generated MCP servers to your OpenClaw config to let your agent interact with Avalanche dApps directly.

## Marketplace

Browse and publish MCP servers for Avalanche dApps:

```bash
# Start the marketplace
uv run python cli.py serve --port 3000

# Open http://localhost:3000
```

Publish your generated MCP server:
```bash
uv run python cli.py publish \
  --name "Trader Joe Router" \
  --description "DEX on Avalanche — swap tokens, add/remove liquidity" \
  --contracts 0x60aE616a2155Ee3d9A68541Ba4544862310933d4 \
  --tags dex,swap,defi
```

## Supported Avalanche dApps

| dApp | Type | Command |
|------|------|---------|
| Trader Joe | DEX | `generate trader_joe_router` |
| Trader Joe V2 | DEX (LB) | `generate trader_joe_router_v2` |
| Pangolin | DEX | `generate pangolin_router` |
| Benqi | Lending | `generate benqi_comptroller` |
| Aave V3 | Lending | `generate aave_pool` |
| Stargate | Bridge | `generate stargate_router` |
| Any contract | — | `generate 0xYourAddress` |

## Auto-Detection

AvaPilot automatically identifies contract types:

- **ERC-20 Tokens** — balanceOf, transfer, approve
- **DEX Routers** — swap, addLiquidity, removeLiquidity
- **NFTs (ERC-721)** — ownerOf, tokenURI, safeTransferFrom
- **Lending Protocols** — deposit, borrow, repay, liquidate
- **Staking Contracts** — stake, unstake, getReward
- **Custom** — any verified contract works

## How It Works

1. **Fetch** — pulls ABI from Snowtrace (Avalanche's block explorer)
2. **Analyze** — identifies contract type, categorizes functions as read/write
3. **Generate** — creates a standalone MCP server with typed tools for every function
4. **Output** — ready-to-run Python server, no dependencies on AvaPilot at runtime

## Project Structure

```
avapilot/
├── avapilot/
│   ├── generator/       ← ABI → MCP server code generation
│   ├── runtime/         ← shared EVM interaction + chain config
│   └── marketplace/     ← browse/publish MCP servers
├── cli.py               ← command-line interface
├── examples/            ← pre-generated MCP servers
└── pyproject.toml
```

## Requirements

- Python 3.9+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Security

- **No private keys** — AvaPilot never touches your wallet
- **Unsigned transactions** — write tools return raw tx data, you sign and broadcast
- **Read-only generation** — the generator only reads public ABI data from Snowtrace
- **Standalone output** — generated servers have no dependency on AvaPilot

## Contributing

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/my-feature`)
3. Commit changes (`git commit -m 'Add feature'`)
4. Push (`git push origin feature/my-feature`)
5. Open a Pull Request

## License

MIT

---

Built for the Avalanche ecosystem 🔺
