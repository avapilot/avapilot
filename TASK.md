# AvaPilot MCP Generator — Build Task

## What to Build
An MCP (Model Context Protocol) server generator that takes smart contract addresses on Avalanche and generates ready-to-use MCP servers. Plus a simple marketplace for discovering/publishing generated MCP servers.

## Architecture

```
avapilot/
├── avapilot/
│   ├── __init__.py
│   ├── generator/
│   │   ├── __init__.py
│   │   ├── abi_fetcher.py      ← fetch ABI from Snowtrace (reuse backend/orchestrator/tools.py logic)
│   │   ├── analyzer.py         ← contract type detection (reuse backend/orchestrator/contract_analyzer.py)
│   │   ├── mcp_builder.py      ← ABI → MCP server code generator (THE CORE)
│   │   └── templates/          ← Jinja2 or string templates for generated server files
│   │       ├── server.py.j2
│   │       ├── tools.py.j2
│   │       ├── requirements.txt.j2
│   │       └── README.md.j2
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── evm.py              ← shared EVM interaction (web3 read/write/simulate)
│   │   └── config.py           ← network config (Avalanche mainnet/fuji, extensible to other EVM)
│   └── marketplace/
│       ├── __init__.py
│       ├── app.py              ← FastAPI app for marketplace
│       ├── registry.py         ← CRUD for dApp listings (SQLite backend)
│       ├── search.py           ← search/filter listings
│       ├── models.py           ← Pydantic models
│       └── static/
│           └── index.html      ← simple browse/search/submit frontend
├── cli.py                      ← CLI entry point: avapilot generate, avapilot publish, avapilot serve
├── examples/
│   └── trader-joe/             ← pre-generated example
├── pyproject.toml              ← package config, dependencies
└── README.md                   ← updated project README
```

## Existing Code to Reuse
All in `backend/orchestrator/`:

1. **tools.py** — `get_contract_abi_impl()`, `get_source_code_impl()`, `read_contract_function_impl()`, `generate_transaction_impl()` — core blockchain interaction
2. **contract_analyzer.py** — `identify_contract_type()`, `explain_contract()` — ABI analysis
3. **network_config.py** — Avalanche mainnet/fuji config with Snowtrace API
4. **knowledge_pipeline.py** (in backend/eleven_agent/) — contract analysis → markdown doc generation

## What the Generator Does

Given a contract address:
1. Fetch ABI from Snowtrace
2. Analyze: identify contract type, extract functions, categorize (read vs write)
3. Generate a complete MCP server folder:
   - `server.py` — MCP server using the `mcp` Python SDK (FastMCP)
   - Each ABI function becomes an MCP tool with:
     - Typed parameters (from ABI inputs)
     - Descriptions (auto-generated from function signatures + contract type context)
     - Read functions → direct call, return result
     - Write functions → build unsigned tx, return tx object for user to sign
   - `requirements.txt` — mcp, web3, etc.
   - `README.md` — how to run, connect to Claude/OpenClaw

Example generated tool for a DEX router:
```python
@mcp.tool()
async def swap_exact_tokens_for_tokens(
    amount_in: int,
    amount_out_min: int, 
    path: list[str],
    to: str,
    deadline: int
) -> dict:
    """Swap exact amount of input tokens for output tokens.
    
    Args:
        amount_in: Amount of input tokens (in wei)
        amount_out_min: Minimum output tokens (slippage protection)
        path: Token addresses for swap route [tokenIn, ..., tokenOut]
        to: Recipient address
        deadline: Unix timestamp deadline
    """
    return build_transaction(
        contract_address=CONTRACT_ADDRESS,
        function_name="swapExactTokensForTokens",
        args=[amount_in, amount_out_min, path, to, deadline]
    )
```

## What the Marketplace Does

Simple web app:
- **Browse** — list published MCP servers with name, description, contract addresses, install command
- **Search** — filter by name, contract type, chain
- **Publish** — submit your generated MCP server (name, description, contracts, repo URL)
- **Install** — copy-paste config for Claude Desktop / OpenClaw

Data stored in SQLite. No auth for v1 (anyone can submit).

Frontend: single-page vanilla HTML/JS. Clean, minimal. Shows cards for each listing.

## CLI Commands

```bash
# Generate MCP server from contract
python cli.py generate 0xContractAddress --chain avalanche --output ./my-dapp-mcp

# Generate with custom name
python cli.py generate 0xContractAddress --name "Trader Joe" --output ./trader-joe-mcp

# Start marketplace server
python cli.py serve --port 3000

# Publish to marketplace (local)
python cli.py publish --name "Trader Joe" --description "DEX on Avalanche" --contracts 0x123... --repo https://github.com/...
```

## Dependencies
- `mcp` (FastMCP Python SDK)
- `web3` 
- `requests`
- `fastapi` + `uvicorn` (marketplace)
- `jinja2` (templates)
- `click` (CLI)
- `pydantic`

## Key Decisions
- NO charging/rate-limiting/auth — this is open source
- NO LLM calls in the generator — pure ABI analysis, deterministic output
- Avalanche-first but chain config is pluggable (just change RPC + explorer URL)
- Generated servers are standalone — no dependency on avapilot package at runtime
- Use FastMCP (the `mcp` package) for generated servers

## Don't
- Don't keep old Flask app, old chat agent, old rate limiter, old error tracker
- Don't add authentication
- Don't add payment/billing
- Don't overcomplicate — this ships in 1-2 weeks
