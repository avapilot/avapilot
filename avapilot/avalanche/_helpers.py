"""Shared helpers, ABIs, and utilities used by all gateway tool modules."""

from decimal import Decimal

from web3 import Web3

from avapilot.avalanche import wallet
from avapilot.runtime.config import (
    get_chain_config,
    CHAINS,
    AVALANCHE_TOKENS,
    AVALANCHE_DAPPS,
)
from avapilot.runtime.evm import fetch_abi


# ── ABIs ─────────────────────────────────────────────────────────────────

ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "totalSupply", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "transfer", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": False, "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
]

WAVAX_ABI = ERC20_ABI + [
    {"constant": False, "inputs": [], "name": "deposit", "outputs": [], "payable": True, "type": "function"},
    {"constant": False, "inputs": [{"name": "wad", "type": "uint256"}], "name": "withdraw", "outputs": [], "type": "function"},
]

TRADER_JOE_ROUTER_ABI = [
    {"inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "amountOutMin", "type": "uint256"}, {"name": "path", "type": "address[]"}, {"name": "to", "type": "address"}, {"name": "deadline", "type": "uint256"}], "name": "swapExactTokensForTokens", "outputs": [{"name": "amounts", "type": "uint256[]"}], "type": "function"},
    {"inputs": [{"name": "amountOutMin", "type": "uint256"}, {"name": "path", "type": "address[]"}, {"name": "to", "type": "address"}, {"name": "deadline", "type": "uint256"}], "name": "swapExactAVAXForTokens", "outputs": [{"name": "amounts", "type": "uint256[]"}], "payable": True, "type": "function"},
    {"inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "amountOutMin", "type": "uint256"}, {"name": "path", "type": "address[]"}, {"name": "to", "type": "address"}, {"name": "deadline", "type": "uint256"}], "name": "swapExactTokensForAVAX", "outputs": [{"name": "amounts", "type": "uint256[]"}], "type": "function"},
    {"inputs": [{"name": "amountIn", "type": "uint256"}, {"name": "path", "type": "address[]"}], "name": "getAmountsOut", "outputs": [{"name": "amounts", "type": "uint256[]"}], "type": "function", "constant": True},
    {"inputs": [], "name": "factory", "outputs": [{"name": "", "type": "address"}], "type": "function", "constant": True},
    {"inputs": [], "name": "WAVAX", "outputs": [{"name": "", "type": "address"}], "type": "function", "constant": True},
]


# ── Helpers ──────────────────────────────────────────────────────────────

_w3_cache: dict[str, Web3] = {}


def get_w3(chain: str = "avalanche") -> Web3:
    """Get a Web3 instance (cached, lazy connection)."""
    if chain in _w3_cache:
        return _w3_cache[chain]
    config = get_chain_config(chain)
    rpcs = [config['rpc_url']]
    if chain == 'avalanche':
        rpcs.append('https://avalanche-c-chain-rpc.publicnode.com')
        rpcs.append('https://avax.meowrpc.com')
    elif chain == 'fuji':
        rpcs.append('https://avalanche-fuji-c-chain-rpc.publicnode.com')
    for rpc in rpcs:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))
            w3.eth.chain_id  # test connectivity
            _w3_cache[chain] = w3
            return w3
        except Exception:
            continue
    w3 = Web3(Web3.HTTPProvider(rpcs[0], request_kwargs={"timeout": 30}))
    _w3_cache[chain] = w3
    return w3


def resolve_token(symbol_or_address: str) -> str:
    """Resolve a token symbol or address to a checksummed address."""
    upper = symbol_or_address.upper()
    if upper == "AVAX":
        upper = "WAVAX"
    if upper in AVALANCHE_TOKENS:
        return Web3.to_checksum_address(AVALANCHE_TOKENS[upper])
    for key, addr in AVALANCHE_TOKENS.items():
        if key.upper() == upper:
            return Web3.to_checksum_address(addr)
    if symbol_or_address.startswith("0x") and len(symbol_or_address) == 42:
        return Web3.to_checksum_address(symbol_or_address)
    raise ValueError(
        f"Unknown token '{symbol_or_address}'. Known tokens: {', '.join(AVALANCHE_TOKENS.keys())}. "
        f"Or pass a contract address (0x...)."
    )


def require_wallet() -> None:
    """Raise if wallet is not configured."""
    if not wallet.is_wallet_configured():
        raise RuntimeError(
            "Wallet not configured. Set AVAPILOT_PRIVATE_KEY environment variable."
        )


def token_decimals(token_address: str, w3: Web3) -> int:
    """Get decimals for a token."""
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
    )
    return contract.functions.decimals().call()


def to_token_units(amount, decimals: int) -> int:
    """Convert human-readable amount to token base units."""
    return int(Decimal(str(amount)) * Decimal(10**decimals))


def from_token_units(raw: int, decimals: int) -> float:
    """Convert token base units to human-readable amount."""
    return raw / (10**decimals)


def get_swap_path(token_in: str, token_out: str) -> list[str]:
    """Build a swap path, routing through WAVAX if neither token is WAVAX."""
    wavax = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
    addr_in = resolve_token(token_in)
    addr_out = resolve_token(token_out)

    if addr_in == wavax or addr_out == wavax:
        return [addr_in, addr_out]
    return [addr_in, wavax, addr_out]
