"""
Contract analyzer — identifies contract type and categorizes functions.
"""


# Signature sets for known contract types
CONTRACT_SIGNATURES = {
    "ERC20_TOKEN": {
        "required": {"balanceOf", "transfer", "approve", "allowance", "totalSupply"},
        "confidence": 0.95,
        "description": "ERC-20 fungible token",
    },
    "DEX_ROUTER": {
        "required": set(),
        "match_any_2": {"swapExactTokensForTokens", "addLiquidity", "removeLiquidity", "swapExactAVAXForTokens", "swapExactETHForTokens"},
        "confidence": 0.85,
        "description": "DEX router for token swapping",
    },
    "ERC721_NFT": {
        "required": set(),
        "match_any_2": {"ownerOf", "safeTransferFrom", "tokenURI", "mint"},
        "confidence": 0.90,
        "description": "ERC-721 non-fungible token (NFT)",
    },
    "ERC1155": {
        "required": set(),
        "match_any_2": {"balanceOf", "balanceOfBatch", "safeTransferFrom", "uri"},
        "confidence": 0.85,
        "description": "ERC-1155 multi-token",
    },
    "STAKING": {
        "required": set(),
        "match_any_2": {"stake", "unstake", "getReward", "earned", "withdraw"},
        "confidence": 0.80,
        "description": "Staking/farming contract",
    },
    "LENDING": {
        "required": set(),
        "match_any_2": {"deposit", "borrow", "repay", "liquidate", "withdraw"},
        "confidence": 0.80,
        "description": "Lending/borrowing protocol",
    },
}


def identify_contract_type(abi: list) -> dict:
    """Identify contract type from ABI function signatures."""
    functions = {item["name"] for item in abi if item.get("type") == "function"}

    for ctype, spec in CONTRACT_SIGNATURES.items():
        required = spec.get("required", set())
        if required and required.issubset(functions):
            return {
                "type": ctype,
                "confidence": spec["confidence"],
                "description": spec["description"],
                "matched": list(required & functions),
            }

        match_any = spec.get("match_any_2", set())
        if match_any:
            matched = match_any & functions
            if len(matched) >= 2:
                return {
                    "type": ctype,
                    "confidence": spec["confidence"],
                    "description": spec["description"],
                    "matched": list(matched),
                }

    return {"type": "CUSTOM", "confidence": 0.0, "description": "Custom contract", "matched": []}


def categorize_functions(abi: list) -> dict:
    """Categorize ABI functions into read/write/events."""
    read_funcs = []
    write_funcs = []
    events = []

    for item in abi:
        if item.get("type") == "event":
            events.append(item)
        elif item.get("type") == "function":
            if item.get("stateMutability") in ("view", "pure"):
                read_funcs.append(item)
            else:
                write_funcs.append(item)

    return {"read": read_funcs, "write": write_funcs, "events": events}


def solidity_type_to_python(sol_type: str) -> str:
    """Convert Solidity type to Python type hint."""
    if sol_type.startswith("uint") or sol_type.startswith("int"):
        return "int"
    elif sol_type == "address":
        return "str"
    elif sol_type == "bool":
        return "bool"
    elif sol_type == "string":
        return "str"
    elif sol_type.startswith("bytes"):
        return "str"
    elif sol_type.endswith("[]"):
        inner = solidity_type_to_python(sol_type[:-2])
        return f"list[{inner}]"
    elif sol_type == "tuple":
        return "list"
    else:
        return "str"


def function_to_tool_name(func_name: str) -> str:
    """Convert camelCase function name to snake_case tool name."""
    import re
    # Insert underscore before uppercase letters
    s1 = re.sub(r"([A-Z])", r"_\1", func_name)
    return s1.lower().strip("_")
