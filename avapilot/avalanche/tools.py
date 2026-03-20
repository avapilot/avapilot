"""
Full Avalanche MCP Gateway — wallet, swaps, transfers, contracts, gas, L1 cross-chain.

Gives AI agents complete access to the Avalanche network via MCP tools.
Includes read-only queries, token transfers, DEX swaps, contract interactions,
and wallet management.
"""

import json
import time

from web3 import Web3
from mcp.server.fastmcp import FastMCP

from avapilot.avalanche import pchain, glacier, wallet
from avapilot.runtime.config import (
    get_chain_config,
    CHAINS,
    AVALANCHE_TOKENS,
    AVALANCHE_DAPPS,
)
from avapilot.runtime.evm import fetch_abi

mcp = FastMCP("AvaPilot Avalanche Gateway")


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

def _get_w3(chain: str = "avalanche") -> Web3:
    """Get a Web3 instance (cached, lazy connection)."""
    if chain in _w3_cache:
        return _w3_cache[chain]
    config = get_chain_config(chain)
    # Try primary, fall back to alternative public RPC
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
    # Last resort: return without testing (will fail on actual call)
    w3 = Web3(Web3.HTTPProvider(rpcs[0], request_kwargs={"timeout": 30}))
    _w3_cache[chain] = w3
    return w3


def _resolve_token(symbol_or_address: str) -> str:
    """Resolve a token symbol or address to a checksummed address."""
    upper = symbol_or_address.upper()
    if upper == "AVAX":
        upper = "WAVAX"
    if upper in AVALANCHE_TOKENS:
        return Web3.to_checksum_address(AVALANCHE_TOKENS[upper])
    # Check case-sensitive keys (e.g., BTC.b, WETH.e)
    for key, addr in AVALANCHE_TOKENS.items():
        if key.upper() == upper:
            return Web3.to_checksum_address(addr)
    if symbol_or_address.startswith("0x") and len(symbol_or_address) == 42:
        return Web3.to_checksum_address(symbol_or_address)
    raise ValueError(
        f"Unknown token '{symbol_or_address}'. Known tokens: {', '.join(AVALANCHE_TOKENS.keys())}. "
        f"Or pass a contract address (0x...)."
    )


def _require_wallet() -> None:
    """Raise if wallet is not configured."""
    if not wallet.is_wallet_configured():
        raise RuntimeError(
            "Wallet not configured. Set AVAPILOT_PRIVATE_KEY environment variable."
        )


def _token_decimals(token_address: str, w3: Web3) -> int:
    """Get decimals for a token."""
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=ERC20_ABI
    )
    return contract.functions.decimals().call()


def _to_token_units(amount, decimals: int) -> int:
    """Convert human-readable amount to token base units."""
    from decimal import Decimal
    return int(Decimal(str(amount)) * Decimal(10**decimals))


def _from_token_units(raw: int, decimals: int) -> float:
    """Convert token base units to human-readable amount."""
    return raw / (10**decimals)


# ── Network Info ─────────────────────────────────────────────────────────


@mcp.tool()
def avalanche_network_info() -> dict:
    """Get Avalanche network overview: P-Chain height, current supply, and chain count."""
    try:
        height = pchain.get_height()
    except Exception:
        height = None

    try:
        supply_navax = pchain.get_current_supply()
        supply_avax = int(supply_navax) / 1e9
    except Exception:
        supply_avax = None

    try:
        blockchains = pchain.get_blockchains()
        chain_count = len(blockchains)
    except Exception:
        chain_count = None

    return {
        "network": "Avalanche Mainnet",
        "p_chain_height": height,
        "current_supply_avax": supply_avax,
        "blockchain_count": chain_count,
    }


@mcp.tool()
def avalanche_list_l1s() -> list[dict]:
    """List all Avalanche L1 chains tracked by Glacier."""
    try:
        chains = glacier.list_chains()
        return [
            {
                "chain_id": c.get("chainId"),
                "chain_name": c.get("chainName"),
                "network_token": c.get("networkToken", {}).get("symbol"),
                "rpc_url": c.get("rpcUrl"),
            }
            for c in chains
        ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def avalanche_get_l1_info(chain_id_or_name: str) -> dict:
    """Get details about a specific Avalanche L1 chain by chain ID or name."""
    try:
        return glacier.get_chain_info(chain_id_or_name)
    except Exception:
        pass

    try:
        chains = glacier.list_chains()
        name_lower = chain_id_or_name.lower()
        for c in chains:
            if name_lower in c.get("chainName", "").lower():
                return c
        return {"error": f"No chain found matching '{chain_id_or_name}'"}
    except Exception as e:
        return {"error": str(e)}


# ── Validators & Staking ────────────────────────────────────────────────


@mcp.tool()
def avalanche_list_validators(subnet_id: str | None = None, limit: int = 20) -> list[dict]:
    """List current Avalanche validators. Optionally filter by subnet ID."""
    try:
        validators = pchain.get_current_validators(subnet_id=subnet_id, limit=limit)
        return [
            {
                "node_id": v.get("nodeID"),
                "start_time": v.get("startTime"),
                "end_time": v.get("endTime"),
                "stake_amount": v.get("stakeAmount"),
                "uptime": v.get("uptime"),
                "connected": v.get("connected"),
            }
            for v in validators[:limit]
        ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def avalanche_validator_info(node_id: str) -> dict:
    """Get details about a specific validator by node ID."""
    try:
        validators = pchain.get_current_validators()
        for v in validators:
            if v.get("nodeID") == node_id:
                return {
                    "node_id": v.get("nodeID"),
                    "start_time": v.get("startTime"),
                    "end_time": v.get("endTime"),
                    "stake_amount": v.get("stakeAmount"),
                    "uptime": v.get("uptime"),
                    "connected": v.get("connected"),
                    "delegation_fee": v.get("delegationFee"),
                    "delegator_count": len(v.get("delegators", []) or []),
                }
        return {"error": f"Validator {node_id} not found"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def avalanche_staking_info() -> dict:
    """Get staking overview: min stake amounts, total staked, staking asset."""
    result = {}
    try:
        min_stake = pchain.get_min_stake()
        result["min_validator_stake_avax"] = int(min_stake["minValidatorStake"]) / 1e9
        result["min_delegator_stake_avax"] = int(min_stake["minDelegatorStake"]) / 1e9
    except Exception:
        pass

    try:
        total = pchain.get_total_stake()
        result["total_staked_avax"] = int(total) / 1e9
    except Exception:
        pass

    try:
        result["staking_asset_id"] = pchain.get_staking_asset_id()
    except Exception:
        pass

    return result


@mcp.tool()
def estimate_staking_rewards(amount_avax: float, duration_days: int) -> dict:
    """Estimate AVAX staking rewards for a given amount and duration.

    Uses approximate mainnet reward rate (~8-10% APY).
    Actual rewards depend on uptime and network conditions.
    """
    if amount_avax <= 0:
        return {"error": "amount_avax must be positive"}
    if duration_days < 14:
        return {"error": "Minimum staking duration is 14 days"}
    if duration_days > 365:
        return {"error": "Maximum staking duration is 365 days"}

    # Approximate reward rate (annualized)
    annual_rate = 0.09  # ~9% APY estimate
    daily_rate = annual_rate / 365
    estimated_reward = amount_avax * daily_rate * duration_days

    return {
        "staked_avax": amount_avax,
        "duration_days": duration_days,
        "estimated_reward_avax": round(estimated_reward, 6),
        "estimated_apy_percent": round(annual_rate * 100, 2),
        "note": "Estimate only. Actual rewards depend on uptime, delegation fee, and network conditions.",
    }


# ── Token & Balance Queries ─────────────────────────────────────────────


@mcp.tool()
def avalanche_get_balance(address: str, chain_id: str = "43114") -> dict:
    """Get native + ERC-20 token balances for an address on an Avalanche chain."""
    result = {}
    try:
        native = glacier.get_native_balance(chain_id, address)
        result["native"] = native
    except Exception as e:
        result["native_error"] = str(e)

    try:
        erc20 = glacier.get_erc20_balances(chain_id, address)
        result["erc20"] = erc20
    except Exception as e:
        result["erc20_error"] = str(e)

    return result


@mcp.tool()
def avalanche_get_nfts(address: str, chain_id: str = "43114") -> dict:
    """Get NFT holdings for an address on an Avalanche chain."""
    try:
        return glacier.list_nfts(chain_id, address)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def avalanche_token_transfers(address: str, chain_id: str = "43114") -> dict:
    """Get recent token transfers for an address on an Avalanche chain."""
    result = {}
    try:
        result["native_transfers"] = glacier.list_transactions(chain_id, address)
    except Exception as e:
        result["native_error"] = str(e)

    try:
        result["erc20_transfers"] = glacier.list_erc20_transfers(chain_id, address)
    except Exception as e:
        result["erc20_error"] = str(e)

    return result


# ── Cross-Chain ──────────────────────────────────────────────────────────


@mcp.tool()
def avalanche_list_blockchains() -> list[dict]:
    """List all blockchains registered on the Avalanche network."""
    try:
        blockchains = pchain.get_blockchains()
        return [
            {
                "id": bc.get("id"),
                "name": bc.get("name"),
                "subnet_id": bc.get("subnetID"),
                "vm_id": bc.get("vmID"),
            }
            for bc in blockchains
        ]
    except Exception as e:
        return [{"error": str(e)}]


@mcp.tool()
def avalanche_get_blockchain_status(blockchain_id: str) -> dict:
    """Check the status of a specific blockchain (Validating, Created, etc.)."""
    try:
        status = pchain.get_blockchain_status(blockchain_id)
        return {"blockchain_id": blockchain_id, "status": status}
    except Exception as e:
        return {"error": str(e)}


# ── Wallet Tools ─────────────────────────────────────────────────────────


@mcp.tool()
def wallet_status() -> dict:
    """Check if wallet is configured, show address and AVAX balance."""
    if not wallet.is_wallet_configured():
        return {
            "configured": False,
            "message": "No wallet configured. Set AVAPILOT_PRIVATE_KEY environment variable.",
        }

    address = wallet.get_address()
    result = {"configured": True, "address": address}

    try:
        w3 = _get_w3()
        balance_wei = w3.eth.get_balance(address)
        result["avax_balance"] = _from_token_units(balance_wei, 18)
    except Exception as e:
        result["balance_error"] = str(e)

    return result


@mcp.tool()
def wallet_address() -> dict:
    """Return the connected wallet address."""
    _require_wallet()
    return {"address": wallet.get_address()}


# ── Send / Transfer Tools ───────────────────────────────────────────────


@mcp.tool()
def send_avax(to_address: str, amount_avax: float) -> dict:
    """Send native AVAX to an address. Amount in AVAX (e.g., 1.5)."""
    _require_wallet()
    to = Web3.to_checksum_address(to_address)
    value_wei = _to_token_units(amount_avax, 18)

    w3 = _get_w3()
    sender = wallet.get_address()
    balance = w3.eth.get_balance(sender)
    if balance < value_wei:
        return {
            "error": f"Insufficient AVAX balance. Have {_from_token_units(balance, 18):.6f}, need {amount_avax}",
        }

    gas_price = w3.eth.gas_price
    estimated_gas = 21_000
    total_cost = value_wei + (gas_price * estimated_gas)
    print(f"[send_avax] Sending {amount_avax} AVAX to {to}")
    print(f"  Gas: {estimated_gas} units @ {_from_token_units(gas_price, 9):.2f} gwei")
    print(f"  Total cost: ~{_from_token_units(total_cost, 18):.6f} AVAX")

    tx = {"to": to, "value": value_wei, "gas": estimated_gas}
    tx_hash = wallet.sign_and_send(tx)
    receipt = wallet.wait_for_receipt(tx_hash)

    return {
        "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
        "status": "success" if receipt.get("status") == 1 else "failed",
        "amount_avax": amount_avax,
        "to": to,
        "gas_used": receipt.get("gasUsed"),
    }


@mcp.tool()
def send_token(token_symbol_or_address: str, to_address: str, amount: float) -> dict:
    """Send ERC-20 tokens to an address. Amount in human-readable units (e.g., 100 USDC)."""
    _require_wallet()
    token_addr = _resolve_token(token_symbol_or_address)
    to = Web3.to_checksum_address(to_address)

    w3 = _get_w3()
    contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    decimals = contract.functions.decimals().call()
    symbol = contract.functions.symbol().call()
    raw_amount = _to_token_units(amount, decimals)

    sender = wallet.get_address()
    balance = contract.functions.balanceOf(sender).call()
    if balance < raw_amount:
        return {
            "error": f"Insufficient {symbol} balance. Have {_from_token_units(balance, decimals)}, need {amount}",
        }

    print(f"[send_token] Sending {amount} {symbol} to {to}")

    tx_data = contract.functions.transfer(to, raw_amount).build_transaction({
        "from": sender,
        "nonce": w3.eth.get_transaction_count(sender),
        "chainId": get_chain_config("avalanche")["chain_id"],
        "gasPrice": w3.eth.gas_price,
    })
    tx_hash = wallet.sign_and_send(tx_data)
    receipt = wallet.wait_for_receipt(tx_hash)

    return {
        "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
        "status": "success" if receipt.get("status") == 1 else "failed",
        "amount": amount,
        "token": symbol,
        "to": to,
        "gas_used": receipt.get("gasUsed"),
    }


@mcp.tool()
def wrap_avax(amount_avax: float) -> dict:
    """Wrap AVAX to WAVAX. Amount in AVAX (e.g., 1.5)."""
    _require_wallet()
    wavax_addr = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
    value_wei = _to_token_units(amount_avax, 18)

    w3 = _get_w3()
    sender = wallet.get_address()
    balance = w3.eth.get_balance(sender)
    if balance < value_wei:
        return {"error": f"Insufficient AVAX. Have {_from_token_units(balance, 18):.6f}, need {amount_avax}"}

    contract = w3.eth.contract(address=wavax_addr, abi=WAVAX_ABI)
    print(f"[wrap_avax] Wrapping {amount_avax} AVAX to WAVAX")

    tx_data = contract.functions.deposit().build_transaction({
        "from": sender,
        "value": value_wei,
        "nonce": w3.eth.get_transaction_count(sender),
        "chainId": get_chain_config("avalanche")["chain_id"],
        "gasPrice": w3.eth.gas_price,
    })
    tx_hash = wallet.sign_and_send(tx_data)
    receipt = wallet.wait_for_receipt(tx_hash)

    return {
        "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
        "status": "success" if receipt.get("status") == 1 else "failed",
        "amount_avax": amount_avax,
        "wavax_address": wavax_addr,
    }


@mcp.tool()
def unwrap_avax(amount_wavax: float) -> dict:
    """Unwrap WAVAX back to native AVAX. Amount in WAVAX (e.g., 1.5)."""
    _require_wallet()
    wavax_addr = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
    raw_amount = _to_token_units(amount_wavax, 18)

    w3 = _get_w3()
    sender = wallet.get_address()
    contract = w3.eth.contract(address=wavax_addr, abi=WAVAX_ABI)
    balance = contract.functions.balanceOf(sender).call()
    if balance < raw_amount:
        return {"error": f"Insufficient WAVAX. Have {_from_token_units(balance, 18):.6f}, need {amount_wavax}"}

    print(f"[unwrap_avax] Unwrapping {amount_wavax} WAVAX to AVAX")

    tx_data = contract.functions.withdraw(raw_amount).build_transaction({
        "from": sender,
        "nonce": w3.eth.get_transaction_count(sender),
        "chainId": get_chain_config("avalanche")["chain_id"],
        "gasPrice": w3.eth.gas_price,
    })
    tx_hash = wallet.sign_and_send(tx_data)
    receipt = wallet.wait_for_receipt(tx_hash)

    return {
        "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
        "status": "success" if receipt.get("status") == 1 else "failed",
        "amount_wavax": amount_wavax,
    }


# ── Token Tools ──────────────────────────────────────────────────────────


@mcp.tool()
def approve_token(token_address: str, spender_address: str, amount: float) -> dict:
    """Approve an address to spend ERC-20 tokens on your behalf. Amount in human-readable units."""
    _require_wallet()
    token_addr = _resolve_token(token_address)
    spender = Web3.to_checksum_address(spender_address)

    w3 = _get_w3()
    contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    decimals = contract.functions.decimals().call()
    symbol = contract.functions.symbol().call()
    raw_amount = _to_token_units(amount, decimals)

    sender = wallet.get_address()
    print(f"[approve_token] Approving {spender} to spend {amount} {symbol}")

    tx_data = contract.functions.approve(spender, raw_amount).build_transaction({
        "from": sender,
        "nonce": w3.eth.get_transaction_count(sender),
        "chainId": get_chain_config("avalanche")["chain_id"],
        "gasPrice": w3.eth.gas_price,
    })
    tx_hash = wallet.sign_and_send(tx_data)
    receipt = wallet.wait_for_receipt(tx_hash)

    return {
        "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
        "status": "success" if receipt.get("status") == 1 else "failed",
        "token": symbol,
        "spender": spender,
        "amount_approved": amount,
    }


@mcp.tool()
def token_allowance(token_address: str, owner: str, spender: str) -> dict:
    """Check how many tokens an owner has approved a spender to use."""
    token_addr = _resolve_token(token_address)
    owner_addr = Web3.to_checksum_address(owner)
    spender_addr = Web3.to_checksum_address(spender)

    w3 = _get_w3()
    contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
    decimals = contract.functions.decimals().call()
    symbol = contract.functions.symbol().call()
    raw_allowance = contract.functions.allowance(owner_addr, spender_addr).call()

    return {
        "token": symbol,
        "token_address": token_addr,
        "owner": owner_addr,
        "spender": spender_addr,
        "allowance": _from_token_units(raw_allowance, decimals),
        "allowance_raw": str(raw_allowance),
    }


@mcp.tool()
def token_info(token_symbol_or_address: str) -> dict:
    """Get token info: name, symbol, decimals, total supply."""
    token_addr = _resolve_token(token_symbol_or_address)
    w3 = _get_w3()
    contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)

    try:
        name = contract.functions.name().call()
    except Exception:
        name = "Unknown"
    try:
        symbol = contract.functions.symbol().call()
    except Exception:
        symbol = "Unknown"
    try:
        decimals = contract.functions.decimals().call()
    except Exception:
        decimals = 18
    try:
        total_supply_raw = contract.functions.totalSupply().call()
        total_supply = _from_token_units(total_supply_raw, decimals)
    except Exception:
        total_supply = None

    return {
        "address": token_addr,
        "name": name,
        "symbol": symbol,
        "decimals": decimals,
        "total_supply": total_supply,
    }


# ── DEX / Swap Tools (Trader Joe) ───────────────────────────────────────


def _get_swap_path(token_in: str, token_out: str) -> list[str]:
    """Build a swap path, routing through WAVAX if neither token is WAVAX."""
    wavax = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
    addr_in = _resolve_token(token_in)
    addr_out = _resolve_token(token_out)

    if addr_in == wavax or addr_out == wavax:
        return [addr_in, addr_out]
    return [addr_in, wavax, addr_out]


@mcp.tool()
def get_swap_quote(amount_in: float, token_in: str, token_out: str) -> dict:
    """Get expected output amount for a swap on Trader Joe. Amount in human-readable units."""
    router_addr = Web3.to_checksum_address(AVALANCHE_DAPPS["trader_joe_router"])
    path = _get_swap_path(token_in, token_out)

    w3 = _get_w3()
    in_decimals = _token_decimals(path[0], w3) if path[0] != Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"]) else 18
    out_decimals = _token_decimals(path[-1], w3) if path[-1] != Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"]) else 18

    # For AVAX input, use 18 decimals
    addr_in = _resolve_token(token_in)
    wavax = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
    if token_in.upper() == "AVAX":
        in_decimals = 18
        path[0] = wavax

    raw_in = _to_token_units(amount_in, in_decimals)

    router = w3.eth.contract(address=router_addr, abi=TRADER_JOE_ROUTER_ABI)
    amounts = router.functions.getAmountsOut(raw_in, path).call()
    raw_out = amounts[-1]

    return {
        "amount_in": amount_in,
        "token_in": token_in,
        "amount_out": _from_token_units(raw_out, out_decimals),
        "token_out": token_out,
        "path": path,
        "router": router_addr,
    }


@mcp.tool()
def swap_exact_tokens(
    amount_in: float,
    token_in: str,
    token_out: str,
    slippage_percent: float = 0.5,
) -> dict:
    """Swap tokens on Trader Joe. Amount in human-readable units. Slippage default 0.5%.

    Handles AVAX<->token and token<->token swaps automatically.
    """
    _require_wallet()
    router_addr = Web3.to_checksum_address(AVALANCHE_DAPPS["trader_joe_router"])
    wavax = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
    w3 = _get_w3()
    sender = wallet.get_address()
    deadline = int(time.time()) + 1200  # 20 minutes

    is_avax_in = token_in.upper() == "AVAX"
    is_avax_out = token_out.upper() == "AVAX"

    if is_avax_in:
        path = [wavax, _resolve_token(token_out)]
        in_decimals = 18
    elif is_avax_out:
        path = [_resolve_token(token_in), wavax]
        in_decimals = _token_decimals(path[0], w3)
    else:
        path = _get_swap_path(token_in, token_out)
        in_decimals = _token_decimals(path[0], w3)

    out_decimals = 18 if is_avax_out else _token_decimals(path[-1], w3)
    raw_in = _to_token_units(amount_in, in_decimals)

    # Get quote for slippage calculation
    router = w3.eth.contract(address=router_addr, abi=TRADER_JOE_ROUTER_ABI)
    amounts = router.functions.getAmountsOut(raw_in, path).call()
    expected_out = amounts[-1]
    min_out = int(expected_out * (1 - slippage_percent / 100))

    print(f"[swap] {amount_in} {token_in} -> ~{_from_token_units(expected_out, out_decimals)} {token_out}")
    print(f"  Min output (after {slippage_percent}% slippage): {_from_token_units(min_out, out_decimals)}")
    print(f"  Path: {' -> '.join(path)}")

    chain_id = get_chain_config("avalanche")["chain_id"]
    nonce = w3.eth.get_transaction_count(sender)
    gas_price = w3.eth.gas_price

    if is_avax_in:
        tx_data = router.functions.swapExactAVAXForTokens(
            min_out, path, sender, deadline
        ).build_transaction({
            "from": sender,
            "value": raw_in,
            "nonce": nonce,
            "chainId": chain_id,
            "gasPrice": gas_price,
        })
    elif is_avax_out:
        tx_data = router.functions.swapExactTokensForAVAX(
            raw_in, min_out, path, sender, deadline
        ).build_transaction({
            "from": sender,
            "nonce": nonce,
            "chainId": chain_id,
            "gasPrice": gas_price,
        })
    else:
        tx_data = router.functions.swapExactTokensForTokens(
            raw_in, min_out, path, sender, deadline
        ).build_transaction({
            "from": sender,
            "nonce": nonce,
            "chainId": chain_id,
            "gasPrice": gas_price,
        })

    tx_hash = wallet.sign_and_send(tx_data)
    receipt = wallet.wait_for_receipt(tx_hash)

    return {
        "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
        "status": "success" if receipt.get("status") == 1 else "failed",
        "amount_in": amount_in,
        "token_in": token_in,
        "expected_out": _from_token_units(expected_out, out_decimals),
        "token_out": token_out,
        "gas_used": receipt.get("gasUsed"),
    }


@mcp.tool()
def get_token_price(token_symbol_or_address: str) -> dict:
    """Get token price in AVAX and USD (estimated) via Trader Joe router."""
    token_addr = _resolve_token(token_symbol_or_address)
    wavax = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
    usdc = Web3.to_checksum_address(AVALANCHE_TOKENS["USDC"])
    router_addr = Web3.to_checksum_address(AVALANCHE_DAPPS["trader_joe_router"])

    w3 = _get_w3()
    router = w3.eth.contract(address=router_addr, abi=TRADER_JOE_ROUTER_ABI)
    decimals = _token_decimals(token_addr, w3) if token_addr != wavax else 18
    one_token = _to_token_units(1, decimals)

    result = {"token": token_symbol_or_address, "address": token_addr}

    if token_addr == wavax:
        result["price_avax"] = 1.0
        # WAVAX->USDC price
        try:
            amounts = router.functions.getAmountsOut(one_token, [wavax, usdc]).call()
            usdc_decimals = _token_decimals(usdc, w3)
            result["price_usd"] = _from_token_units(amounts[-1], usdc_decimals)
        except Exception:
            result["price_usd"] = None
    else:
        # Token->WAVAX price
        try:
            amounts = router.functions.getAmountsOut(one_token, [token_addr, wavax]).call()
            result["price_avax"] = _from_token_units(amounts[-1], 18)
        except Exception:
            result["price_avax"] = None

        # Token->USDC price
        try:
            if token_addr == usdc:
                result["price_usd"] = 1.0
            else:
                path = [token_addr, wavax, usdc] if token_addr != wavax else [wavax, usdc]
                amounts = router.functions.getAmountsOut(one_token, path).call()
                usdc_decimals = _token_decimals(usdc, w3)
                result["price_usd"] = _from_token_units(amounts[-1], usdc_decimals)
        except Exception:
            result["price_usd"] = None

    return result


# ── Contract Tools ───────────────────────────────────────────────────────


@mcp.tool()
def read_contract(
    contract_address: str,
    function_name: str,
    args: list | None = None,
    chain: str = "avalanche",
) -> dict:
    """Call any view/pure function on a contract. Fetches ABI automatically from Snowtrace."""
    config = get_chain_config(chain)
    addr = Web3.to_checksum_address(contract_address)
    args = args or []

    try:
        abi = fetch_abi(addr, config["explorer_api"])
    except Exception as e:
        return {"error": f"Failed to fetch ABI: {e}. Contract may not be verified."}

    from avapilot.runtime.evm import read_contract as evm_read

    try:
        result = evm_read(config["rpc_url"], addr, abi, function_name, args)
        return {"result": result if not isinstance(result, bytes) else result.hex()}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def write_contract(
    contract_address: str,
    function_name: str,
    args: list | None = None,
    value_avax: float = 0,
    chain: str = "avalanche",
) -> dict:
    """Call any write function on a contract. Signs and sends the transaction.

    Fetches ABI automatically. value_avax is the AVAX to send with the call.
    """
    _require_wallet()
    config = get_chain_config(chain)
    addr = Web3.to_checksum_address(contract_address)
    args = args or []

    try:
        abi = fetch_abi(addr, config["explorer_api"])
    except Exception as e:
        return {"error": f"Failed to fetch ABI: {e}. Contract may not be verified."}

    w3 = _get_w3(chain)
    contract = w3.eth.contract(address=addr, abi=abi)
    sender = wallet.get_address()
    value_wei = _to_token_units(value_avax, 18) if value_avax else 0

    # Find the function in ABI
    func_abi = next(
        (item for item in abi if item.get("name") == function_name and item.get("type") == "function"),
        None,
    )
    if not func_abi:
        return {"error": f"Function '{function_name}' not found in contract ABI"}

    # Convert args
    from avapilot.runtime.evm import _convert_args
    converted = _convert_args(args, func_abi.get("inputs", []))

    print(f"[write_contract] Calling {function_name} on {addr}")
    print(f"  Args: {converted}")
    if value_avax:
        print(f"  Value: {value_avax} AVAX")

    tx_data = contract.functions[function_name](*converted).build_transaction({
        "from": sender,
        "value": value_wei,
        "nonce": w3.eth.get_transaction_count(sender),
        "chainId": config["chain_id"],
        "gasPrice": w3.eth.gas_price,
    })
    tx_hash = wallet.sign_and_send(tx_data, chain)
    receipt = wallet.wait_for_receipt(tx_hash, chain)

    return {
        "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
        "status": "success" if receipt.get("status") == 1 else "failed",
        "function": function_name,
        "contract": addr,
        "gas_used": receipt.get("gasUsed"),
    }


@mcp.tool()
def deploy_contract(
    bytecode: str,
    constructor_args: list | None = None,
    value_avax: float = 0,
    abi: list | None = None,
) -> dict:
    """Deploy a smart contract to Avalanche C-Chain.

    bytecode: hex-encoded contract bytecode (with or without 0x prefix).
    constructor_args: arguments for the constructor (if any). Requires abi if used.
    """
    _require_wallet()
    w3 = _get_w3()
    sender = wallet.get_address()
    value_wei = _to_token_units(value_avax, 18) if value_avax else 0

    if not bytecode.startswith("0x"):
        bytecode = "0x" + bytecode

    if constructor_args and abi:
        contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        tx_data = contract.constructor(*constructor_args).build_transaction({
            "from": sender,
            "value": value_wei,
            "nonce": w3.eth.get_transaction_count(sender),
            "chainId": get_chain_config("avalanche")["chain_id"],
            "gasPrice": w3.eth.gas_price,
        })
    else:
        tx_data = {
            "from": sender,
            "value": value_wei,
            "data": bytecode,
            "nonce": w3.eth.get_transaction_count(sender),
            "chainId": get_chain_config("avalanche")["chain_id"],
            "gasPrice": w3.eth.gas_price,
        }
        try:
            tx_data["gas"] = w3.eth.estimate_gas(tx_data)
        except Exception:
            tx_data["gas"] = 3_000_000

    print(f"[deploy_contract] Deploying contract from {sender}")
    print(f"  Bytecode size: {len(bytecode) // 2} bytes")

    tx_hash = wallet.sign_and_send(tx_data)
    receipt = wallet.wait_for_receipt(tx_hash)

    return {
        "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
        "status": "success" if receipt.get("status") == 1 else "failed",
        "contract_address": receipt.get("contractAddress"),
        "gas_used": receipt.get("gasUsed"),
    }


@mcp.tool()
def get_contract_abi(contract_address: str, chain: str = "avalanche") -> dict:
    """Fetch the ABI for a verified contract from Snowtrace."""
    config = get_chain_config(chain)
    addr = Web3.to_checksum_address(contract_address)

    try:
        abi = fetch_abi(addr, config["explorer_api"])
        functions = [
            item["name"]
            for item in abi
            if item.get("type") == "function"
        ]
        return {
            "contract": addr,
            "abi_item_count": len(abi),
            "functions": functions,
            "abi": abi,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Gas Tools ────────────────────────────────────────────────────────────


@mcp.tool()
def estimate_gas(
    to: str,
    data: str = "0x",
    value_avax: float = 0,
) -> dict:
    """Estimate gas for a transaction on Avalanche C-Chain."""
    w3 = _get_w3()
    to_addr = Web3.to_checksum_address(to)
    value_wei = _to_token_units(value_avax, 18) if value_avax else 0

    tx = {"to": to_addr, "value": value_wei, "data": data}
    if wallet.is_wallet_configured():
        tx["from"] = wallet.get_address()

    try:
        gas = w3.eth.estimate_gas(tx)
        gas_price = w3.eth.gas_price
        cost_wei = gas * gas_price
        return {
            "gas_units": gas,
            "gas_price_gwei": _from_token_units(gas_price, 9),
            "estimated_cost_avax": _from_token_units(cost_wei, 18),
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def gas_price() -> dict:
    """Get current gas price on Avalanche C-Chain in gwei and nAVAX."""
    w3 = _get_w3()
    price_wei = w3.eth.gas_price
    return {
        "gas_price_wei": price_wei,
        "gas_price_gwei": _from_token_units(price_wei, 9),
        "gas_price_navax": price_wei,  # 1 wei = 1 nAVAX on Avalanche
    }


# ── L1 / Subnet Tools ───────────────────────────────────────────────────


@mcp.tool()
def get_l1_rpc(chain_id_or_name: str) -> dict:
    """Get the RPC URL for any Avalanche L1 chain."""
    # Check local config first
    for key, cfg in CHAINS.items():
        if str(cfg["chain_id"]) == str(chain_id_or_name) or key == chain_id_or_name.lower():
            return {"chain": cfg["name"], "rpc_url": cfg["rpc_url"], "chain_id": cfg["chain_id"]}

    # Query Glacier
    try:
        info = glacier.get_chain_info(chain_id_or_name)
        rpc = info.get("rpcUrl")
        if rpc:
            return {
                "chain": info.get("chainName", chain_id_or_name),
                "rpc_url": rpc,
                "chain_id": info.get("chainId"),
            }
    except Exception:
        pass

    # Search by name
    try:
        chains = glacier.list_chains()
        name_lower = chain_id_or_name.lower()
        for c in chains:
            if name_lower in c.get("chainName", "").lower():
                return {
                    "chain": c.get("chainName"),
                    "rpc_url": c.get("rpcUrl"),
                    "chain_id": c.get("chainId"),
                }
    except Exception:
        pass

    return {"error": f"No RPC found for '{chain_id_or_name}'"}


@mcp.tool()
def call_l1_contract(
    chain_id: str,
    contract_address: str,
    function_name: str,
    args: list | None = None,
) -> dict:
    """Read from any contract on any Avalanche L1 chain. Fetches ABI from the chain's explorer."""
    args = args or []

    # Find the RPC URL
    rpc_info = get_l1_rpc(chain_id)
    if "error" in rpc_info:
        return rpc_info
    rpc_url = rpc_info["rpc_url"]

    addr = Web3.to_checksum_address(contract_address)

    # Try to find explorer API for ABI
    for key, cfg in CHAINS.items():
        if str(cfg["chain_id"]) == str(chain_id):
            try:
                abi = fetch_abi(addr, cfg["explorer_api"])
                from avapilot.runtime.evm import read_contract as evm_read
                result = evm_read(rpc_url, addr, abi, function_name, args)
                return {"result": result if not isinstance(result, bytes) else result.hex()}
            except Exception as e:
                return {"error": str(e)}

    return {"error": f"No block explorer found for chain {chain_id}. Cannot auto-fetch ABI."}


# ── Utility Tools ────────────────────────────────────────────────────────


@mcp.tool()
def resolve_address(name_or_symbol: str) -> dict:
    """Resolve a token symbol or dApp name to its contract address."""
    # Check tokens
    upper = name_or_symbol.upper()
    for key, addr in AVALANCHE_TOKENS.items():
        if key.upper() == upper:
            return {"type": "token", "name": key, "address": addr}

    # Check dApps
    lower = name_or_symbol.lower().replace(" ", "_").replace("-", "_")
    for key, addr in AVALANCHE_DAPPS.items():
        if key == lower or lower in key:
            return {"type": "dapp", "name": key, "address": addr}

    # Check if it's already an address
    if name_or_symbol.startswith("0x") and len(name_or_symbol) == 42:
        return {"type": "address", "address": Web3.to_checksum_address(name_or_symbol)}

    return {
        "error": f"Cannot resolve '{name_or_symbol}'",
        "known_tokens": list(AVALANCHE_TOKENS.keys()),
        "known_dapps": list(AVALANCHE_DAPPS.keys()),
    }


@mcp.tool()
def tx_status(tx_hash: str, chain: str = "avalanche") -> dict:
    """Check the status and receipt of a transaction."""
    w3 = _get_w3(chain)

    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        return {
            "tx_hash": tx_hash,
            "status": "success" if receipt.get("status") == 1 else "failed",
            "block_number": receipt.get("blockNumber"),
            "gas_used": receipt.get("gasUsed"),
            "contract_address": receipt.get("contractAddress"),
            "from": receipt.get("from"),
            "to": receipt.get("to"),
        }
    except Exception:
        pass

    # Transaction may be pending
    try:
        tx = w3.eth.get_transaction(tx_hash)
        return {
            "tx_hash": tx_hash,
            "status": "pending",
            "from": tx.get("from"),
            "to": tx.get("to"),
            "value_avax": _from_token_units(tx.get("value", 0), 18),
        }
    except Exception as e:
        return {"error": f"Transaction not found: {e}"}


@mcp.tool()
def encode_function_call(
    contract_address: str,
    function_name: str,
    args: list | None = None,
    chain: str = "avalanche",
) -> dict:
    """Encode a function call as calldata without sending it. Useful for multisig or batching."""
    config = get_chain_config(chain)
    addr = Web3.to_checksum_address(contract_address)
    args = args or []

    try:
        abi = fetch_abi(addr, config["explorer_api"])
    except Exception as e:
        return {"error": f"Failed to fetch ABI: {e}"}

    w3 = Web3()
    contract = w3.eth.contract(address=addr, abi=abi)

    func_abi = next(
        (item for item in abi if item.get("name") == function_name and item.get("type") == "function"),
        None,
    )
    if not func_abi:
        return {"error": f"Function '{function_name}' not found in ABI"}

    from avapilot.runtime.evm import _convert_args
    converted = _convert_args(args, func_abi.get("inputs", []))
    calldata = contract.functions[function_name](*converted)._encode_transaction_data()

    return {
        "contract": addr,
        "function": function_name,
        "calldata": calldata,
    }


# ── Server entry point ──────────────────────────────────────────────────


def run_server():
    """Start the Full Avalanche MCP Gateway server."""
    mcp.run()


if __name__ == "__main__":
    run_server()
