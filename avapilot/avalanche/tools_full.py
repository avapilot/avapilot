"""FULL mode tools — deploy/write arbitrary contracts (power user)."""

from web3 import Web3
from mcp.server.fastmcp import FastMCP

from avapilot.avalanche import wallet
from avapilot.avalanche._helpers import (
    get_w3, require_wallet, to_token_units,
)
from avapilot.runtime.config import get_chain_config
from avapilot.runtime.evm import fetch_abi


def register(mcp: FastMCP) -> None:
    """Register power-user tools on the given MCP server."""

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
        require_wallet()
        config = get_chain_config(chain)
        addr = Web3.to_checksum_address(contract_address)
        args = args or []

        try:
            abi = fetch_abi(addr, config["explorer_api"])
        except Exception as e:
            return {"error": f"Failed to fetch ABI: {e}. Contract may not be verified."}

        w3 = get_w3(chain)
        contract = w3.eth.contract(address=addr, abi=abi)
        sender = wallet.get_address()
        value_wei = to_token_units(value_avax, 18) if value_avax else 0

        func_abi = next(
            (item for item in abi if item.get("name") == function_name and item.get("type") == "function"),
            None,
        )
        if not func_abi:
            return {"error": f"Function '{function_name}' not found in contract ABI"}

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
        require_wallet()
        w3 = get_w3()
        sender = wallet.get_address()
        value_wei = to_token_units(value_avax, 18) if value_avax else 0

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
