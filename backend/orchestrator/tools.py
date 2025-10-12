"""
Clean separation:
- @tool functions for LLM to call
- _impl functions for Python to call directly
"""

import re
import time
import traceback
from langchain_core.tools import tool
import requests
import json
from web3 import Web3

# Snowtrace API configuration
SNOWTRACE_API_URL = "https://api.snowtrace.io/api"
SNOWTRACE_API_KEY = "placeholder"

# Hardcoded token addresses for Fuji Testnet
FUJI_TOKEN_ADDRESSES = {
    "WAVAX": "0x1d308089a2d1ced3f1ce36b1fcaf815b07217be3",
    "USDC": "0x5425890298aed601595a70AB815c96711a31Bc65"
}

# RPC endpoint
FUJI_RPC_URL = "https://api.avax-test.network/ext/bc/C/rpc"


# ============================================
# IMPLEMENTATION FUNCTIONS (No @tool decorator)
# ============================================

def get_token_address_impl(token_symbol: str) -> str:
    """Implementation that can be called from Python directly"""
    address = FUJI_TOKEN_ADDRESSES.get(token_symbol.upper(), "Error: Token not found.")
    print(f"  [IMPL] get_token_address({token_symbol}) → {address}")
    return address


def get_contract_abi_impl(contract_address: str) -> str:
    """Implementation that can be called from Python directly"""
    print(f"  [IMPL] get_contract_abi({contract_address})")
    
    params = {
        "module": "contract",
        "action": "getabi",
        "address": contract_address,
        "apikey": SNOWTRACE_API_KEY
    }

    try:
        response = requests.get(SNOWTRACE_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if data["status"] == "1":
            abi_length = len(data["result"])
            print(f"  [IMPL] ✓ ABI fetched ({abi_length} characters)")
            return data["result"]
        else:
            error = f"Error fetching ABI: {data['message']} - {data['result']}"
            print(f"  [IMPL] ✗ {error}")
            return error
            
    except requests.exceptions.RequestException as e:
        error = f"Error: Network request failed: {e}"
        print(f"  [IMPL] ✗ {error}")
        return error
    except json.JSONDecodeError:
        error = "Error: Failed to parse response from block explorer."
        print(f"  [IMPL] ✗ {error}")
        return error


def read_contract_function_impl(
    contract_address: str,
    function_name: str,
    function_args: list
) -> dict:
    """
    Implementation for reading contract state (view/pure functions only).
    Simple and direct - no agent needed!
    """
    print(f"\n{'='*60}")
    print(f"[READ] {function_name} on {contract_address}")
    print(f"{'='*60}")
    print(f"  Args: {function_args}")
    
    try:
        # Connect to RPC
        w3 = Web3(Web3.HTTPProvider(FUJI_RPC_URL))
        if not w3.is_connected():
            return {"success": False, "error": "RPC connection failed"}
        
        print(f"  ✓ Connected to Avalanche Fuji")
        
        # Get ABI
        abi = get_contract_abi_impl(contract_address)
        if abi.startswith("Error"):
            return {"success": False, "error": abi}
        
        contract_abi = json.loads(abi)
        
        # Clean ABI (same logic as generate_transaction_impl)
        cleaned_abi = []
        for item in contract_abi:
            cleaned_item = dict(item)
            
            if 'inputs' in cleaned_item:
                cleaned_inputs = []
                for inp in cleaned_item['inputs']:
                    cleaned_inp = dict(inp)
                    if 'type' not in cleaned_inp and 'internalType' in cleaned_inp:
                        cleaned_inp['type'] = cleaned_inp['internalType']
                    cleaned_inputs.append(cleaned_inp)
                cleaned_item['inputs'] = cleaned_inputs
            
            if 'outputs' in cleaned_item:
                cleaned_outputs = []
                for out in cleaned_item['outputs']:
                    cleaned_out = dict(out)
                    if 'type' not in cleaned_out and 'internalType' in cleaned_out:
                        cleaned_out['type'] = cleaned_out['internalType']
                    cleaned_outputs.append(cleaned_out)
                cleaned_item['outputs'] = cleaned_outputs
            
            cleaned_abi.append(cleaned_item)
        
        print(f"  ✓ ABI parsed and cleaned")
        
        # Find function
        function_abi = None
        for item in cleaned_abi:
            if item.get('name') == function_name:
                state_mutability = item.get('stateMutability', '')
                if state_mutability not in ['view', 'pure']:
                    return {
                        "success": False,
                        "error": f"'{function_name}' is not a read-only function (mutability: {state_mutability})"
                    }
                function_abi = item
                break
        
        if not function_abi:
            return {"success": False, "error": f"Function '{function_name}' not found in ABI"}
        
        print(f"  ✓ Function found (read-only)")
        
        # Convert arguments to proper types
        converted_args = []
        for arg, param in zip(function_args, function_abi.get('inputs', [])):
            param_type = param['type']
            
            if param_type.startswith('uint') or param_type.startswith('int'):
                converted = int(float(arg)) if isinstance(arg, (str, float)) else arg
            elif param_type == 'address':
                converted = Web3.to_checksum_address(arg.lower()) if isinstance(arg, str) else arg
            elif param_type == 'address[]':
                converted = [Web3.to_checksum_address(a.lower()) for a in arg] if isinstance(arg, list) else arg
            elif param_type == 'bool':
                converted = bool(arg) if not isinstance(arg, str) else arg.lower() in ['true', '1', 'yes']
            else:
                converted = arg
            
            converted_args.append(converted)
        
        print(f"  ✓ Arguments converted: {converted_args}")
        
        # Create contract and call
        contract_address = Web3.to_checksum_address(contract_address.lower())
        contract = w3.eth.contract(address=contract_address, abi=cleaned_abi)
        
        print(f"  → Calling {function_name}({converted_args})...")
        result = contract.functions[function_name](*converted_args).call()
        
        print(f"  ✓ Result: {result} (type: {type(result).__name__})")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "result": str(result),  # Convert to string for JSON serialization
            "result_type": type(result).__name__
        }
        
    except Exception as e:
        error_msg = f"Read failed: {str(e)}"
        print(f"  ✗ {error_msg}")
        traceback.print_exc()
        print(f"{'='*60}\n")
        return {"success": False, "error": error_msg}


def generate_transaction_impl(
    contract_address: str,
    abi: str,
    function_name: str,
    function_args: list,
    value_in_avax: float = 0.0
) -> dict:
    """Implementation for generating transactions"""
    print(f"\n{'='*60}")
    print(f"[IMPL] generate_transaction")
    print(f"{'='*60}")
    print(f"  Function: {function_name}")
    print(f"  Contract: {contract_address}")
    print(f"  Value: {value_in_avax} AVAX")
    print(f"  Raw args: {function_args}")
    
    try:
        w3 = Web3()
        
        # Parse and validate ABI
        contract_abi = json.loads(abi)
        print(f"  ✓ ABI parsed ({len(contract_abi)} functions)")
        
        # Clean ABI
        cleaned_abi = []
        for item in contract_abi:
            cleaned_item = dict(item)
            
            if 'inputs' in cleaned_item:
                cleaned_inputs = []
                for inp in cleaned_item['inputs']:
                    cleaned_inp = dict(inp)
                    if 'type' not in cleaned_inp and 'internalType' in cleaned_inp:
                        cleaned_inp['type'] = cleaned_inp['internalType']
                    cleaned_inputs.append(cleaned_inp)
                cleaned_item['inputs'] = cleaned_inputs
            
            if 'outputs' in cleaned_item:
                cleaned_outputs = []
                for out in cleaned_item['outputs']:
                    cleaned_out = dict(out)
                    if 'type' not in cleaned_out and 'internalType' in cleaned_out:
                        cleaned_out['type'] = cleaned_out['internalType']
                    cleaned_outputs.append(cleaned_out)
                cleaned_item['outputs'] = cleaned_outputs
            
            cleaned_abi.append(cleaned_item)
        
        contract_abi = cleaned_abi
        print(f"  ✓ ABI validated and cleaned")
        
        # Find function
        function_abi = None
        for item in contract_abi:
            if item.get('name') == function_name and item.get('type') == 'function':
                function_abi = item
                break
        
        if not function_abi:
            raise ValueError(f"Function '{function_name}' not found in ABI")
        
        print(f"  ✓ Function found in ABI")
        
        # Convert arguments
        converted_args = []
        for i, (arg, param) in enumerate(zip(function_args, function_abi['inputs'])):
            param_type = param['type']
            
            if param_type.startswith('uint') or param_type.startswith('int'):
                converted = int(float(arg)) if isinstance(arg, (str, float)) else arg
            elif param_type == 'address':
                converted = Web3.to_checksum_address(arg.lower()) if isinstance(arg, str) else arg
            elif param_type == 'address[]':
                converted = [Web3.to_checksum_address(addr.lower()) if isinstance(addr, str) else addr for addr in arg] if isinstance(arg, list) else arg
            elif param_type == 'bool':
                converted = bool(arg) if not isinstance(arg, str) else arg.lower() in ['true', '1', 'yes']
            else:
                converted = arg
            
            converted_args.append(converted)
        
        print(f"  ✓ All arguments converted")
        
        # Create contract and encode
        contract_address = Web3.to_checksum_address(contract_address.lower())
        contract = w3.eth.contract(address=contract_address, abi=contract_abi)
        
        contract_function = contract.functions[function_name](*converted_args)
        encoded_data = contract_function._encode_transaction_data()
        
        value_in_wei = w3.to_wei(value_in_avax, 'ether')
        
        tx_object = {
            "to": contract_address,
            "value": hex(value_in_wei),
            "data": encoded_data
        }
        
        print(f"  ✓✓✓ SUCCESS: Transaction generated")
        print(f"    Data: {encoded_data[:66]}... ({len(encoded_data)} chars)")
        print(f"{'='*60}\n")
        
        return {
            "success": True,
            "transaction": tx_object
        }
        
    except Exception as e:
        error_msg = f"Failed to generate transaction: {str(e)}"
        print(f"  ✗✗✗ ERROR: {error_msg}")
        traceback.print_exc()
        print(f"{'='*60}\n")
        
        return {
            "success": False,
            "error": error_msg
        }


# ============================================
# TOOL WRAPPERS (For LLM to call)
# ============================================

@tool
def get_token_address(token_symbol: str) -> str:
    """
    Finds the contract address for a given token symbol on the Fuji Testnet.
    Supports: WAVAX, USDC
    
    Args:
        token_symbol: Token symbol (e.g., "WAVAX", "USDC")
    
    Returns:
        Contract address string or error message
    """
    print(f"[TOOL] get_token_address called: {token_symbol}")
    return get_token_address_impl(token_symbol)


@tool
def get_contract_abi(contract_address: str) -> str:
    """
    Fetches the ABI (Application Binary Interface) for a given smart contract.
    Use this to understand what functions a contract has.
    
    Args:
        contract_address: The contract address to fetch ABI for
        
    Returns:
        ABI JSON string or error message
    """
    print(f"[TOOL] get_contract_abi called: {contract_address}")
    return get_contract_abi_impl(contract_address)


@tool
def read_contract_function(
    contract_address: str,
    function_name: str,
    function_args: list
) -> str:
    """
    Reads data from a smart contract (view/pure functions only).
    
    Common use cases:
    - Check token balance: read_contract_function("0xUSDC...", "balanceOf", ["0xUserAddr..."])
    - Check allowance: read_contract_function("0xUSDC...", "allowance", ["0xOwner...", "0xSpender..."])
    - Get token decimals: read_contract_function("0xUSDC...", "decimals", [])
    - Get token symbol: read_contract_function("0xUSDC...", "symbol", [])
    
    Args:
        contract_address: Contract to read from
        function_name: Function to call (must be view/pure)
        function_args: Arguments as list (use [] for functions with no arguments)
        
    Returns:
        JSON string with {"success": true, "result": "..."} or {"success": false, "error": "..."}
    """
    print(f"[TOOL] read_contract_function called: {function_name} on {contract_address}")
    result = read_contract_function_impl(contract_address, function_name, function_args)
    return json.dumps(result)


# NOTE: generate_transaction is NOT exposed as a @tool here
# It's wrapped in transaction_tool.py as generate_blockchain_transaction