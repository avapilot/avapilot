from __future__ import annotations
"""
Shared EVM interaction utilities — ABI fetching, contract reading, tx building.
"""

import json
import requests
from web3 import Web3


def fetch_abi(contract_address: str, explorer_api_url: str, api_key: str = "") -> list:
    """Fetch ABI from block explorer (Snowtrace, Etherscan, etc.)."""
    params = {
        "module": "contract",
        "action": "getabi",
        "address": contract_address,
        "apikey": api_key or "YourApiKeyToken",
    }
    resp = requests.get(explorer_api_url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data["status"] != "1":
        raise RuntimeError(f"Failed to fetch ABI: {data.get('result', data.get('message', 'Unknown error'))}")

    return json.loads(data["result"])


def fetch_source_code(contract_address: str, explorer_api_url: str, api_key: str = "") -> "str | None":
    """Fetch verified source code from block explorer. Returns None if unverified."""
    params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": contract_address,
        "apikey": api_key or "YourApiKeyToken",
    }
    try:
        resp = requests.get(explorer_api_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data["status"] == "1" and data["result"]:
            source = data["result"][0].get("SourceCode", "")
            if source:
                # Handle JSON-wrapped multi-file sources
                if source.startswith("{"):
                    try:
                        parsed = json.loads(source)
                        if "sources" in parsed:
                            parts = []
                            for fname, content in parsed["sources"].items():
                                parts.append(f"// File: {fname}\n{content.get('content', '')}")
                            return "\n\n".join(parts)
                    except json.JSONDecodeError:
                        pass
                return source
    except Exception:
        pass
    return None


def read_contract(
    rpc_url: str,
    contract_address: str,
    abi: list,
    function_name: str,
    args: list,
) -> any:
    """Call a view/pure function on a contract and return the result."""
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to RPC: {rpc_url}")

    addr = Web3.to_checksum_address(contract_address)
    contract = w3.eth.contract(address=addr, abi=abi)

    # Convert args based on ABI types
    func_abi = next(
        (item for item in abi if item.get("name") == function_name and item.get("type") == "function"),
        None,
    )
    if not func_abi:
        raise ValueError(f"Function '{function_name}' not found in ABI")

    converted = _convert_args(args, func_abi.get("inputs", []))
    result = contract.functions[function_name](*converted).call()
    return result


def build_transaction(
    contract_address: str,
    abi: list,
    function_name: str,
    args: list,
    value_wei: int = 0,
) -> dict:
    """Build an unsigned transaction for a write function."""
    w3 = Web3()
    addr = Web3.to_checksum_address(contract_address)
    contract = w3.eth.contract(address=addr, abi=abi)

    func_abi = next(
        (item for item in abi if item.get("name") == function_name and item.get("type") == "function"),
        None,
    )
    if not func_abi:
        raise ValueError(f"Function '{function_name}' not found in ABI")

    converted = _convert_args(args, func_abi.get("inputs", []))
    encoded = contract.functions[function_name](*converted)._encode_transaction_data()

    return {
        "to": addr,
        "value": hex(value_wei),
        "data": encoded,
    }


def _convert_args(args: list, input_specs: list) -> list:
    """Convert string args to proper types based on ABI input specs."""
    converted = []
    for arg, spec in zip(args, input_specs):
        ptype = spec.get("type", "")
        if ptype.startswith("uint") or ptype.startswith("int"):
            converted.append(int(float(arg)) if isinstance(arg, (str, float)) else arg)
        elif ptype == "address":
            converted.append(Web3.to_checksum_address(str(arg).lower()))
        elif ptype == "address[]":
            converted.append([Web3.to_checksum_address(str(a).lower()) for a in arg])
        elif ptype == "bool":
            if isinstance(arg, str):
                converted.append(arg.lower() in ("true", "1", "yes"))
            else:
                converted.append(bool(arg))
        else:
            converted.append(arg)
    return converted
