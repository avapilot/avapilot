"""
Full Avalanche MCP Gateway — backward-compatible entry point.

Delegates to gateway.create_gateway("full") for all 35 tools.
New code should use ``avapilot.avalanche.gateway.create_gateway(mode)`` directly.
"""

from avapilot.avalanche.gateway import create_gateway

mcp = create_gateway("full")


def run_server():
    """Start the Full Avalanche MCP Gateway server (all tools)."""
    mcp.run()


if __name__ == "__main__":
    run_server()
