"""
AvaPilot CLI — Generate MCP servers from smart contracts.

Usage:
    python cli.py generate 0xContractAddress --chain avalanche --output ./my-mcp
    python cli.py serve --port 3000
    python cli.py publish --name "My dApp" --contracts 0x123...
"""

import argparse
import sys
import os

# Add avapilot to path
sys.path.insert(0, os.path.dirname(__file__))


def cmd_generate(args):
    """Generate an MCP server from a contract address."""
    from avapilot.generator.abi_fetcher import fetch_contract_data
    from avapilot.generator.mcp_builder import generate_mcp_server
    from avapilot.generator.analyzer import identify_contract_type, categorize_functions

    from avapilot.generator.avalanche import resolve_dapp_name, get_known_contract_info
    raw = args.address
    address = resolve_dapp_name(raw) or raw
    if address != raw:
        print(f"   Resolved \"{raw}\" → {address}")
    chain = args.chain
    output = args.output or f"./{address[:10]}-mcp"
    name = args.name
    api_key = args.api_key or os.getenv("SNOWTRACE_API_KEY", "")

    print(f"🚀 AvaPilot MCP Generator")
    print(f"   Contract: {address}")
    print(f"   Chain:    {chain}")
    print(f"   Output:   {output}")
    print()

    # Fetch contract data
    print("📡 Fetching contract ABI...")
    try:
        contract_data = fetch_contract_data(address, chain, api_key)
    except Exception as e:
        print(f"❌ Failed to fetch contract: {e}")
        sys.exit(1)

    abi = contract_data["abi"]
    contract_type = identify_contract_type(abi)
    categories = categorize_functions(abi)

    print(f"✅ ABI fetched ({len(abi)} items)")
    print(f"   Type: {contract_type['description']} (confidence: {int(contract_type['confidence'] * 100)}%)")
    print(f"   Verified: {'✅' if contract_data['verified'] else '⚠️  No'}")
    print(f"   Read functions: {len(categories['read'])}")
    print(f"   Write functions: {len(categories['write'])}")
    print(f"   Events: {len(categories['events'])}")
    print()

    # Generate MCP server
    print("🔨 Generating MCP server...")
    generate_mcp_server(contract_data, output, name)

    print(f"✅ MCP server generated at: {output}/")
    print()
    print("📋 Next steps:")
    print(f"   cd {output}")
    print(f"   uv run server.py")
    print()
    print("   Or: pip install -r requirements.txt && python server.py")
    print("   See README.md for Claude Desktop / OpenClaw setup.")


def cmd_serve(args):
    """Start the marketplace server."""
    from avapilot.marketplace.app import create_app
    import uvicorn

    port = args.port or 3000
    print(f"🏪 Starting AvaPilot Marketplace on port {port}...")
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=port)


def cmd_publish(args):
    """Publish an MCP server to the marketplace."""
    import requests as http_requests
    import json

    url = args.marketplace_url or "http://localhost:3000"
    
    payload = {
        "name": args.name,
        "description": args.description or "",
        "contracts": args.contracts.split(",") if args.contracts else [],
        "chain": args.chain,
        "repo_url": args.repo or "",
        "tags": args.tags.split(",") if args.tags else [],
    }

    print(f"📤 Publishing '{args.name}' to {url}...")
    try:
        resp = http_requests.post(f"{url}/api/listings", json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        print(f"✅ Published! ID: {data.get('id')}")
    except Exception as e:
        print(f"❌ Failed to publish: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="avapilot",
        description="AvaPilot — MCP Server Generator for Avalanche dApps",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = subparsers.add_parser("generate", help="Generate MCP server from contract")
    gen.add_argument("address", help="Contract address (0x...)")
    gen.add_argument("--chain", default="avalanche", help="Chain name (default: avalanche)")
    gen.add_argument("--output", "-o", help="Output directory")
    gen.add_argument("--name", "-n", help="Human-friendly name")
    gen.add_argument("--api-key", help="Block explorer API key")
    gen.set_defaults(func=cmd_generate)

    # serve
    srv = subparsers.add_parser("serve", help="Start marketplace server")
    srv.add_argument("--port", "-p", type=int, default=3000, help="Port (default: 3000)")
    srv.set_defaults(func=cmd_serve)

    # publish
    pub = subparsers.add_parser("publish", help="Publish MCP server to marketplace")
    pub.add_argument("--name", required=True, help="dApp name")
    pub.add_argument("--description", "-d", help="Description")
    pub.add_argument("--contracts", "-c", help="Comma-separated contract addresses")
    pub.add_argument("--chain", default="avalanche", help="Chain")
    pub.add_argument("--repo", help="GitHub repo URL")
    pub.add_argument("--tags", help="Comma-separated tags")
    pub.add_argument("--marketplace-url", default="http://localhost:3000", help="Marketplace URL")
    pub.set_defaults(func=cmd_publish)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
