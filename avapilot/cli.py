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


def cmd_tools(args):
    """Start the Avalanche MCP Gateway in the selected mode."""
    from avapilot.avalanche.gateway import create_gateway

    mode = args.mode
    labels = {
        "read": "READ mode — safe queries only, no wallet needed",
        "trade": "TRADE mode — read + send/swap/approve (wallet required)",
        "full": "FULL mode — everything including deploy/write contracts",
    }
    import sys
    print(f"🔺 Starting Avalanche MCP Gateway", file=sys.stderr)
    print(f"   {labels[mode]}", file=sys.stderr)
    print(file=sys.stderr)
    gateway = create_gateway(mode)
    gateway.run()


def cmd_info(args):
    """Print Avalanche network info."""
    from avapilot.avalanche import pchain, glacier

    print("🔺 Avalanche Network Info")
    print()

    try:
        height = pchain.get_height()
        print(f"   P-Chain height:    {height:,}")
    except Exception as e:
        print(f"   P-Chain height:    error ({e})")

    try:
        validators = pchain.get_current_validators()
        print(f"   Validators:        {len(validators):,}")
    except Exception as e:
        print(f"   Validators:        error ({e})")

    try:
        supply = pchain.get_current_supply()
        avax = int(supply) / 1e9
        print(f"   Current supply:    {avax:,.2f} AVAX")
    except Exception as e:
        print(f"   Current supply:    error ({e})")

    try:
        total = pchain.get_total_stake()
        staked_avax = int(total) / 1e9
        print(f"   Total staked:      {staked_avax:,.2f} AVAX")
    except Exception as e:
        print(f"   Total staked:      error ({e})")

    try:
        blockchains = pchain.get_blockchains()
        print(f"   Blockchains:       {len(blockchains)}")
    except Exception as e:
        print(f"   Blockchains:       error ({e})")

    try:
        subnets = pchain.get_subnets()
        print(f"   Subnets:           {len(subnets)}")
    except Exception as e:
        print(f"   Subnets:           error ({e})")

    try:
        chains = glacier.list_chains()
        print(f"   L1 chains:         {len(chains)} (via Glacier)")
    except Exception as e:
        print(f"   L1 chains:         error ({e})")

    print()


def cmd_register(args):
    """Register a service (dApp/contract) in the local registry."""
    from avapilot.registry import ServiceRegistry

    registry = ServiceRegistry()

    name = args.name

    # Build contracts list
    addresses = [a.strip() for a in args.addresses.split(",")]
    labels = [l.strip() for l in args.labels.split(",")] if args.labels else [f"contract{i}" for i in range(len(addresses))]

    if len(labels) == 1 and len(addresses) == 1:
        labels = ["main"]

    contracts = [{"address": addr, "label": lbl} for addr, lbl in zip(addresses, labels)]

    print(f"📝 Registering '{name}'...")
    for c in contracts:
        print(f"   {c['label']}: {c['address']}")

    try:
        service = registry.register(
            name=name,
            contracts=contracts,
            chain=args.chain,
            description=args.description or "",
            category=args.category or "",
            website=args.website or "",
        )
        print()
        print(f"✅ Registered '{service.name}' (id: {service.id})")
        print(f"   Category:    {service.category or '(none)'}")
        print(f"   Contracts:   {len(service.contracts)}")
        print(f"   Read tools:  {service.total_read_tools}")
        print(f"   Write tools: {service.total_write_tools}")
        for c in service.contracts:
            print(f"   → {c.label}: {c.contract_type} ({len(c.read_functions)}R / {len(c.write_functions)}W)")
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        sys.exit(1)


def cmd_services(args):
    """List all registered services."""
    from avapilot.registry import ServiceRegistry

    registry = ServiceRegistry()
    services = registry.list_services(
        category=args.category,
        search=args.search,
    )

    if not services:
        print("No services registered. Run: python cli.py seed")
        return

    print(f"📦 Registered Services ({len(services)})")
    print()
    for s in services:
        contracts = len(s.contracts)
        print(f"  {s.name} [{s.category or 'uncategorized'}]")
        print(f"    {s.description[:80]}" if s.description else "")
        print(f"    {contracts} contract(s) — {s.total_read_tools}R / {s.total_write_tools}W tools")
        print()


def cmd_seed(args):
    """Seed the registry with well-known Avalanche dApps."""
    from avapilot.registry import ServiceRegistry
    from avapilot.registry.seed import seed_registry

    registry = ServiceRegistry()
    print("🌱 Seeding registry with known Avalanche dApps...")
    print()

    added = seed_registry(registry)

    if added:
        for name in added:
            print(f"   ✅ {name}")
        print()
        print(f"Added {len(added)} service(s).")
    else:
        print("   All services already registered.")


def cmd_scan(args):
    """Scan any contract address — instant analysis, no registration needed."""
    from avapilot.runtime.evm import fetch_abi, fetch_source_code
    from avapilot.runtime.config import get_chain_config
    from avapilot.generator.analyzer import identify_contract_type, categorize_functions

    chain = args.chain or "avalanche"
    cfg = get_chain_config(chain)
    addr = args.address

    print(f"\n🔍 Scanning {addr} on {cfg['name']}...")
    print()

    # Source info
    try:
        import requests, json
        params = {"module": "contract", "action": "getsourcecode", "address": addr, "apikey": "YourApiKeyToken"}
        r = requests.get(cfg["explorer_api"], params=params, timeout=15)
        info = r.json()["result"][0]
        name = info.get("ContractName", "")
        is_proxy = info.get("Proxy") == "1"
        impl = info.get("Implementation", "")
        compiler = info.get("CompilerVersion", "")
        verified = bool(info.get("SourceCode"))

        if name:
            print(f"   Name:       {name}")
        print(f"   Verified:   {'✅ Yes' if verified else '❌ No'}")
        if is_proxy:
            print(f"   Proxy:      ✅ Yes → {impl}")
        if compiler:
            print(f"   Compiler:   {compiler}")
    except Exception as e:
        print(f"   ⚠️  Could not fetch source info: {e}")

    # Fetch ABI (with proxy resolution)
    try:
        abi = fetch_abi(addr, cfg["explorer_api"])
    except Exception as e:
        print(f"\n   ❌ Cannot fetch ABI: {e}")
        print(f"      Contract may not be verified on {cfg['explorer_url']}")
        return

    # Analyze
    analysis = identify_contract_type(abi)
    cats = categorize_functions(abi)
    contract_type = analysis.get("type", "Unknown")
    read_fns = cats.get("read", [])
    write_fns = cats.get("write", [])

    print(f"   Type:       {contract_type}")
    print(f"   Functions:  {len(read_fns)} read, {len(write_fns)} write")

    # Balance check
    try:
        from web3 import Web3
        from avapilot.avalanche._helpers import get_w3, from_token_units
        w3 = get_w3(chain)
        balance = w3.eth.get_balance(Web3.to_checksum_address(addr))
        if balance > 0:
            print(f"   Balance:    {from_token_units(balance, 18):.4f} AVAX")
    except:
        pass

    print()

    if read_fns:
        print("   📖 Read Functions:")
        for fn in read_fns:
            inputs = ", ".join(f"{i.get('name', 'arg')}: {i['type']}" for i in fn.get("inputs", []))
            outputs = ", ".join(o["type"] for o in fn.get("outputs", []))
            print(f"      {fn['name']}({inputs}) → {outputs}")
        print()

    if write_fns:
        print("   ✏️  Write Functions:")
        for fn in write_fns[:15]:
            inputs = ", ".join(f"{i.get('name', 'arg')}: {i['type']}" for i in fn.get("inputs", []))
            print(f"      {fn['name']}({inputs})")
        if len(write_fns) > 15:
            print(f"      ... and {len(write_fns) - 15} more")
        print()

    print(f"   💡 To add this to your gateway:")
    print(f"      python cli.py register \"{name or 'MyService'}\" {addr}")
    print()


def cmd_inspect(args):
    """Inspect a registered service — show contracts and all tools."""
    from avapilot.registry import ServiceRegistry

    registry = ServiceRegistry()
    service = registry.get_service(args.name)

    if not service:
        print(f"❌ Service '{args.name}' not found.")
        sys.exit(1)

    print(f"🔍 {service.name}")
    print(f"   ID:          {service.id}")
    print(f"   Category:    {service.category or '(none)'}")
    print(f"   Description: {service.description}")
    if service.website:
        print(f"   Website:     {service.website}")
    print(f"   Read tools:  {service.total_read_tools}")
    print(f"   Write tools: {service.total_write_tools}")
    print()

    for c in service.contracts:
        print(f"   📄 {c.label} — {c.address}")
        print(f"      Type: {c.contract_type}")
        if c.read_functions:
            print(f"      Read:  {', '.join(c.read_functions[:10])}")
            if len(c.read_functions) > 10:
                print(f"             ... and {len(c.read_functions) - 10} more")
        if c.write_functions:
            print(f"      Write: {', '.join(c.write_functions[:10])}")
            if len(c.write_functions) > 10:
                print(f"             ... and {len(c.write_functions) - 10} more")
        print()



def cmd_api(args):
    """Start the AvaPilot REST API server."""
    from avapilot.api import run_api
    run_api(port=args.port)

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

    # tools / gateway
    tools = subparsers.add_parser("tools", help="Start the Avalanche MCP Gateway")
    tools.add_argument(
        "--mode", "-m",
        choices=["read", "trade", "full"],
        default="read",
        help="Capability mode: read (default), trade, or full",
    )
    tools.set_defaults(func=cmd_tools)

    gateway = subparsers.add_parser("gateway", help="Start the Avalanche MCP Gateway (alias for tools)")
    gateway.add_argument(
        "--mode", "-m",
        choices=["read", "trade", "full"],
        default="read",
        help="Capability mode: read (default), trade, or full",
    )
    gateway.set_defaults(func=cmd_tools)

    # info
    info = subparsers.add_parser("info", help="Print Avalanche network info")
    info.set_defaults(func=cmd_info)

    # register
    reg = subparsers.add_parser("register", help="Register a service (dApp/contract)")
    reg.add_argument("name", help="Service name (e.g. 'Trader Joe')")
    reg.add_argument("addresses", help="Contract address(es), comma-separated")
    reg.add_argument("--labels", help="Comma-separated labels for each address (e.g. router,factory)")
    reg.add_argument("--chain", default="avalanche", help="Chain (default: avalanche)")
    reg.add_argument("--description", "-d", help="Description")
    reg.add_argument("--category", help="Category (DeFi, NFT, Gaming, Token, Infrastructure)")
    reg.add_argument("--website", help="Website URL")
    reg.set_defaults(func=cmd_register)

    # services
    svc = subparsers.add_parser("services", help="List registered services")
    svc.add_argument("--category", help="Filter by category")
    svc.add_argument("--search", "-s", help="Search by name or description")
    svc.set_defaults(func=cmd_services)

    # seed
    sd = subparsers.add_parser("seed", help="Seed registry with known Avalanche dApps")
    sd.set_defaults(func=cmd_seed)

    # scan (no registration needed)
    sc = subparsers.add_parser("scan", help="Scan any contract — instant analysis")
    sc.add_argument("address", help="Contract address (0x...)")
    sc.add_argument("--chain", default="avalanche", help="Chain (default: avalanche)")
    sc.set_defaults(func=cmd_scan)

    # api
    ap = subparsers.add_parser("api", help="Start REST API server for gateway-ui")
    ap.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    ap.set_defaults(func=cmd_api)

    # inspect
    ins = subparsers.add_parser("inspect", help="Inspect a registered service")
    ins.add_argument("name", help="Service name or ID")
    ins.set_defaults(func=cmd_inspect)

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
