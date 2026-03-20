"""
AvaPilot Gateway — mode-based MCP server factory.

Modes:
  read  — safe queries only, no wallet needed (default)
  trade — read + send/swap/approve tokens (wallet required)
  full  — trade + deploy/write arbitrary contracts (power user)
"""

from mcp.server.fastmcp import FastMCP

from avapilot.avalanche import tools_read, tools_trade, tools_full

MODES = {"read", "trade", "full"}

MODE_DESCRIPTIONS = {
    "read": "AvaPilot Gateway (read-only)",
    "trade": "AvaPilot Gateway (trade)",
    "full": "AvaPilot Gateway (full)",
}


def create_gateway(mode: str = "read") -> FastMCP:
    """Create an MCP server with the requested capability level.

    Modes are additive:
      read  → read tools only
      trade → read + trade tools
      full  → read + trade + full tools
    """
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}. Choose from: {', '.join(sorted(MODES))}")

    mcp = FastMCP(MODE_DESCRIPTIONS[mode])

    # Read tools are always included
    tools_read.register(mcp)

    if mode in ("trade", "full"):
        tools_trade.register(mcp)

    if mode == "full":
        tools_full.register(mcp)

    return mcp
