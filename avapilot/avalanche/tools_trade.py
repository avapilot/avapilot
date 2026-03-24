"""TRADE mode tools — wallet required, send/swap/approve tokens."""

import time

from web3 import Web3
from mcp.server.fastmcp import FastMCP

from avapilot.avalanche import wallet
from avapilot.avalanche._helpers import (
    get_w3, resolve_token, require_wallet, token_decimals,
    to_token_units, from_token_units, get_swap_path,
    ERC20_ABI, WAVAX_ABI, TRADER_JOE_ROUTER_ABI,
)
from avapilot.runtime.config import get_chain_config, AVALANCHE_TOKENS, AVALANCHE_DAPPS


def register(mcp: FastMCP) -> None:
    """Register trade tools on the given MCP server."""

    # ── Wallet Tools ─────────────────────────────────────────────────────

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
            w3 = get_w3()
            balance_wei = w3.eth.get_balance(address)
            result["avax_balance"] = from_token_units(balance_wei, 18)
        except Exception as e:
            result["balance_error"] = str(e)
        return result

    @mcp.tool()
    def wallet_address() -> dict:
        """Return the connected wallet address."""
        require_wallet()
        return {"address": wallet.get_address()}

    # ── Send / Transfer Tools ────────────────────────────────────────────

    @mcp.tool()
    def send_avax(to_address: str, amount_avax: float, chain: str = "avalanche") -> dict:
        """Send native AVAX to an address. Amount in AVAX (e.g., 1.5). Use chain=\"fuji\" for testnet."""
        require_wallet()
        to = Web3.to_checksum_address(to_address)
        value_wei = to_token_units(amount_avax, 18)
        w3 = get_w3(chain)
        sender = wallet.get_address()
        balance = w3.eth.get_balance(sender)
        if balance < value_wei:
            return {
                "error": f"Insufficient AVAX balance. Have {from_token_units(balance, 18):.6f}, need {amount_avax}",
            }
        gas_price_val = w3.eth.gas_price
        estimated_gas = 21_000
        total_cost = value_wei + (gas_price_val * estimated_gas)
        print(f"[send_avax] Sending {amount_avax} AVAX to {to}")
        print(f"  Gas: {estimated_gas} units @ {from_token_units(gas_price_val, 9):.2f} gwei")
        print(f"  Total cost: ~{from_token_units(total_cost, 18):.6f} AVAX")
        tx = {"to": to, "value": value_wei, "gas": estimated_gas}
        tx_hash = wallet.sign_and_send(tx, chain=chain)
        receipt = wallet.wait_for_receipt(tx_hash, chain=chain)
        return {
            "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
            "status": "success" if receipt.get("status") == 1 else "failed",
            "amount_avax": amount_avax,
            "to": to,
            "gas_used": receipt.get("gasUsed"),
        }

    @mcp.tool()
    def send_token(token_symbol_or_address: str, to_address: str, amount: float, chain: str = "avalanche") -> dict:
        """Send ERC-20 tokens to an address. Amount in human-readable units (e.g., 100 USDC). Use chain=\"fuji\" for testnet."""
        require_wallet()
        token_addr = resolve_token(token_symbol_or_address)
        to = Web3.to_checksum_address(to_address)
        w3 = get_w3()
        contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
        decimals = contract.functions.decimals().call()
        symbol = contract.functions.symbol().call()
        raw_amount = to_token_units(amount, decimals)
        sender = wallet.get_address()
        balance = contract.functions.balanceOf(sender).call()
        if balance < raw_amount:
            return {
                "error": f"Insufficient {symbol} balance. Have {from_token_units(balance, decimals)}, need {amount}",
            }
        print(f"[send_token] Sending {amount} {symbol} to {to}")
        tx_data = contract.functions.transfer(to, raw_amount).build_transaction({
            "from": sender,
            "nonce": w3.eth.get_transaction_count(sender),
            "chainId": get_chain_config(chain)["chain_id"],
            "gasPrice": w3.eth.gas_price,
        })
        tx_hash = wallet.sign_and_send(tx_data, chain=chain)
        receipt = wallet.wait_for_receipt(tx_hash, chain=chain)
        return {
            "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
            "status": "success" if receipt.get("status") == 1 else "failed",
            "amount": amount,
            "token": symbol,
            "to": to,
            "gas_used": receipt.get("gasUsed"),
        }

    # ── Wrap / Unwrap AVAX ───────────────────────────────────────────────

    @mcp.tool()
    def wrap_avax(amount_avax: float, chain: str = "avalanche") -> dict:
        """Wrap AVAX to WAVAX. Amount in AVAX (e.g., 1.5). Use chain=\"fuji\" for testnet."""
        require_wallet()
        wavax_addr = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
        value_wei = to_token_units(amount_avax, 18)
        w3 = get_w3(chain)
        sender = wallet.get_address()
        balance = w3.eth.get_balance(sender)
        if balance < value_wei:
            return {"error": f"Insufficient AVAX. Have {from_token_units(balance, 18):.6f}, need {amount_avax}"}
        contract = w3.eth.contract(address=wavax_addr, abi=WAVAX_ABI)
        print(f"[wrap_avax] Wrapping {amount_avax} AVAX to WAVAX")
        tx_data = contract.functions.deposit().build_transaction({
            "from": sender,
            "value": value_wei,
            "nonce": w3.eth.get_transaction_count(sender),
            "chainId": get_chain_config(chain)["chain_id"],
            "gasPrice": w3.eth.gas_price,
        })
        tx_hash = wallet.sign_and_send(tx_data, chain=chain)
        receipt = wallet.wait_for_receipt(tx_hash, chain=chain)
        return {
            "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
            "status": "success" if receipt.get("status") == 1 else "failed",
            "amount_avax": amount_avax,
            "wavax_address": wavax_addr,
        }

    @mcp.tool()
    def unwrap_avax(amount_wavax: float, chain: str = "avalanche") -> dict:
        """Unwrap WAVAX back to native AVAX. Amount in WAVAX (e.g., 1.5). Use chain=\"fuji\" for testnet."""
        require_wallet()
        wavax_addr = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
        raw_amount = to_token_units(amount_wavax, 18)
        w3 = get_w3(chain)
        sender = wallet.get_address()
        contract = w3.eth.contract(address=wavax_addr, abi=WAVAX_ABI)
        balance = contract.functions.balanceOf(sender).call()
        if balance < raw_amount:
            return {"error": f"Insufficient WAVAX. Have {from_token_units(balance, 18):.6f}, need {amount_wavax}"}
        print(f"[unwrap_avax] Unwrapping {amount_wavax} WAVAX to AVAX")
        tx_data = contract.functions.withdraw(raw_amount).build_transaction({
            "from": sender,
            "nonce": w3.eth.get_transaction_count(sender),
            "chainId": get_chain_config(chain)["chain_id"],
            "gasPrice": w3.eth.gas_price,
        })
        tx_hash = wallet.sign_and_send(tx_data, chain=chain)
        receipt = wallet.wait_for_receipt(tx_hash, chain=chain)
        return {
            "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
            "status": "success" if receipt.get("status") == 1 else "failed",
            "amount_wavax": amount_wavax,
        }

    # ── Token Approval ───────────────────────────────────────────────────

    @mcp.tool()
    def approve_token(token_address: str, spender_address: str, amount: float, chain: str = "avalanche") -> dict:
        """Approve an address to spend ERC-20 tokens on your behalf. Use chain=\"fuji\" for testnet."""
        require_wallet()
        token_addr = resolve_token(token_address)
        spender = Web3.to_checksum_address(spender_address)
        w3 = get_w3()
        contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
        decimals = contract.functions.decimals().call()
        symbol = contract.functions.symbol().call()
        raw_amount = to_token_units(amount, decimals)
        sender = wallet.get_address()
        print(f"[approve_token] Approving {spender} to spend {amount} {symbol}")
        tx_data = contract.functions.approve(spender, raw_amount).build_transaction({
            "from": sender,
            "nonce": w3.eth.get_transaction_count(sender),
            "chainId": get_chain_config(chain)["chain_id"],
            "gasPrice": w3.eth.gas_price,
        })
        tx_hash = wallet.sign_and_send(tx_data, chain=chain)
        receipt = wallet.wait_for_receipt(tx_hash, chain=chain)
        return {
            "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
            "status": "success" if receipt.get("status") == 1 else "failed",
            "token": symbol,
            "spender": spender,
            "amount_approved": amount,
        }

    # ── DEX Swap ─────────────────────────────────────────────────────────

    @mcp.tool()
    def swap_exact_tokens(
        amount_in: float,
        token_in: str,
        token_out: str,
        slippage_percent: float = 0.5,
        chain: str = "avalanche",
    ) -> dict:
        """Swap tokens on Trader Joe. Amount in human-readable units. Slippage default 0.5%.

        Handles AVAX<->token and token<->token swaps automatically.
        """
        require_wallet()
        router_addr = Web3.to_checksum_address(AVALANCHE_DAPPS["trader_joe_router"])
        wavax = Web3.to_checksum_address(AVALANCHE_TOKENS["WAVAX"])
        w3 = get_w3(chain)
        sender = wallet.get_address()
        deadline = int(time.time()) + 1200

        is_avax_in = token_in.upper() == "AVAX"
        is_avax_out = token_out.upper() == "AVAX"

        if is_avax_in:
            path = [wavax, resolve_token(token_out)]
            in_decimals = 18
        elif is_avax_out:
            path = [resolve_token(token_in), wavax]
            in_decimals = token_decimals(path[0], w3)
        else:
            path = get_swap_path(token_in, token_out)
            in_decimals = token_decimals(path[0], w3)

        out_decimals = 18 if is_avax_out else token_decimals(path[-1], w3)
        raw_in = to_token_units(amount_in, in_decimals)

        router = w3.eth.contract(address=router_addr, abi=TRADER_JOE_ROUTER_ABI)
        amounts = router.functions.getAmountsOut(raw_in, path).call()
        expected_out = amounts[-1]
        min_out = int(expected_out * (1 - slippage_percent / 100))

        print(f"[swap] {amount_in} {token_in} -> ~{from_token_units(expected_out, out_decimals)} {token_out}")
        print(f"  Min output (after {slippage_percent}% slippage): {from_token_units(min_out, out_decimals)}")
        print(f"  Path: {' -> '.join(path)}")

        chain_id = get_chain_config(chain)["chain_id"]
        nonce = w3.eth.get_transaction_count(sender)
        gas_price_val = w3.eth.gas_price

        if is_avax_in:
            tx_data = router.functions.swapExactAVAXForTokens(
                min_out, path, sender, deadline
            ).build_transaction({
                "from": sender,
                "value": raw_in,
                "nonce": nonce,
                "chainId": chain_id,
                "gasPrice": gas_price_val,
            })
        elif is_avax_out:
            tx_data = router.functions.swapExactTokensForAVAX(
                raw_in, min_out, path, sender, deadline
            ).build_transaction({
                "from": sender,
                "nonce": nonce,
                "chainId": chain_id,
                "gasPrice": gas_price_val,
            })
        else:
            tx_data = router.functions.swapExactTokensForTokens(
                raw_in, min_out, path, sender, deadline
            ).build_transaction({
                "from": sender,
                "nonce": nonce,
                "chainId": chain_id,
                "gasPrice": gas_price_val,
            })

        tx_hash = wallet.sign_and_send(tx_data, chain=chain)
        receipt = wallet.wait_for_receipt(tx_hash, chain=chain)

        return {
            "tx_hash": f"0x{tx_hash}" if not tx_hash.startswith("0x") else tx_hash,
            "status": "success" if receipt.get("status") == 1 else "failed",
            "amount_in": amount_in,
            "token_in": token_in,
            "expected_out": from_token_units(expected_out, out_decimals),
            "token_out": token_out,
            "gas_used": receipt.get("gasUsed"),
        }
