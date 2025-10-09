import re
import time
import traceback
from langchain_core.tools import tool
import requests
import json
from web3 import Web3

# We will use the public Snowtrace (Avalanche block explorer) API
SNOWTRACE_API_URL = "https://api.snowtrace.io/api"
SNOWTRACE_API_KEY = "placeholder" 

# This is our simple, hardcoded knowledge base for token addresses on the Fuji Testnet
FUJI_TOKEN_ADDRESSES = {
    "WAVAX": "0x1d308089a2d1ced3f1ce36b1fcaf815b07217be3",
    "USDC": "0x5425890298aed601595a70AB815c96711a31Bc65"
}

@tool
def get_token_address(token_symbol: str) -> str:
    """
    Finds the contract address for a given token symbol on the Fuji Testnet.
    Supports: WAVAX, USDC
    """
    print(f"---TOOL CALLED: get_token_address for symbol: {token_symbol}---")
    address = FUJI_TOKEN_ADDRESSES.get(token_symbol.upper(), "Error: Token not found.")
    print(f"  → Returning: {address}")
    return address

@tool
def get_contract_abi(contract_address: str) -> str:
    """
    Fetches the ABI (Application Binary Interface) for a given smart contract.
    Use this to understand what functions a contract has and to answer questions about it.
    """
    print(f"---TOOL CALLED: get_contract_abi for address: {contract_address}---")

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
            print(f"  → ABI fetched successfully ({abi_length} characters)")
            return data["result"]
        else:
            error = f"Error fetching ABI: {data['message']} - {data['result']}"
            print(f"  → ERROR: {error}")
            return error
    except requests.exceptions.RequestException as e:
        error = f"Error: Network request failed: {e}"
        print(f"  → ERROR: {error}")
        return error
    except json.JSONDecodeError:
        error = "Error: Failed to parse response from block explorer."
        print(f"  → ERROR: {error}")
        return error

@tool
def generate_transaction(
    contract_address: str, 
    abi: str, 
    function_name: str, 
    function_args: list,
    value_in_avax: float = 0.0
) -> str:
    """
    Generates an unsigned transaction for ANY contract function.
    """
    print(f"\n{'='*60}")
    print(f"TOOL CALLED: generate_transaction")
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
        
        # CRITICAL: Clean the ABI by ensuring all input/output parameters have 'type' field
        # This fixes corruption issues from the LLM
        cleaned_abi = []
        for item in contract_abi:
            # Deep copy to avoid modifying original
            cleaned_item = dict(item)
            
            # Fix inputs if they exist
            if 'inputs' in cleaned_item:
                cleaned_inputs = []
                for inp in cleaned_item['inputs']:
                    cleaned_inp = dict(inp)
                    # If 'type' is missing but 'internalType' exists, use that
                    if 'type' not in cleaned_inp and 'internalType' in cleaned_inp:
                        cleaned_inp['type'] = cleaned_inp['internalType']
                        print(f"    ⚠️  Fixed missing type in input: {cleaned_inp.get('name', 'unnamed')}")
                    cleaned_inputs.append(cleaned_inp)
                cleaned_item['inputs'] = cleaned_inputs
            
            # Fix outputs if they exist
            if 'outputs' in cleaned_item:
                cleaned_outputs = []
                for out in cleaned_item['outputs']:
                    cleaned_out = dict(out)
                    if 'type' not in cleaned_out and 'internalType' in cleaned_out:
                        cleaned_out['type'] = cleaned_out['internalType']
                        print(f"    ⚠️  Fixed missing type in output: {cleaned_out.get('name', 'unnamed')}")
                    cleaned_outputs.append(cleaned_out)
                cleaned_item['outputs'] = cleaned_outputs
            
            cleaned_abi.append(cleaned_item)
        
        contract_abi = cleaned_abi
        print(f"  ✓ ABI validated and cleaned")
        
        # Find the function
        function_abi = None
        for item in contract_abi:
            if item.get('name') == function_name and item.get('type') == 'function':
                function_abi = item
                break
        
        if not function_abi:
            raise ValueError(f"Function '{function_name}' not found in ABI")
        
        print(f"  ✓ Function found in ABI")
        expected_params = [f"{p['name']}:{p['type']}" for p in function_abi['inputs']]
        print(f"    Expected params: {expected_params}")
        
        # Convert arguments to proper types
        print(f"\n  → Converting arguments to match ABI types...")
        converted_args = []
        
        for i, (arg, param) in enumerate(zip(function_args, function_abi['inputs'])):
            param_type = param['type']
            param_name = param['name']
            
            print(f"    [{i}] {param_name} ({param_type})")
            print(f"        Input: {arg} (type: {type(arg).__name__})")
            
            if param_type.startswith('uint') or param_type.startswith('int'):
                if isinstance(arg, str):
                    converted = int(float(arg))
                elif isinstance(arg, float):
                    converted = int(arg)
                else:
                    converted = arg
                converted_args.append(converted)
                print(f"        Output: {converted} (type: int)")
                    
            elif param_type == 'address':
                if isinstance(arg, str):
                    # Normalize to lowercase first to handle invalid checksums
                    normalized = arg.lower()
                    # Validate length
                    addr_without_prefix = normalized[2:] if normalized.startswith('0x') else normalized
                    if len(addr_without_prefix) != 40:
                        raise ValueError(f"Invalid address length: {len(addr_without_prefix)} (expected 40)")
                    converted = Web3.to_checksum_address(normalized)
                    converted_args.append(converted)
                    print(f"        Output: {converted} (checksummed)")
                else:
                    converted_args.append(arg)
                    print(f"        Output: {arg} (unchanged)")
                    
            elif param_type == 'address[]':
                if isinstance(arg, list):
                    converted = [Web3.to_checksum_address(addr.lower()) if isinstance(addr, str) else addr for addr in arg]
                    converted_args.append(converted)
                    print(f"        Output: {converted} (checksummed array)")
                else:
                    converted_args.append(arg)
                    print(f"        Output: {arg} (unchanged)")
                    
            elif param_type == 'bool':
                if isinstance(arg, str):
                    converted = arg.lower() in ['true', '1', 'yes']
                else:
                    converted = bool(arg)
                converted_args.append(converted)
                print(f"        Output: {converted} (type: bool)")
                    
            else:
                converted_args.append(arg)
                print(f"        Output: {arg} (unchanged)")
        
        print(f"\n  ✓ All arguments converted successfully")
        print(f"    Final args: {converted_args}")
        
        # Checksum the contract address
        contract_address = Web3.to_checksum_address(contract_address.lower())
        print(f"  ✓ Contract address checksummed: {contract_address}")
        
        # Create contract instance
        contract = w3.eth.contract(address=contract_address, abi=contract_abi)
        print(f"  ✓ Contract instance created")
        
        # Build and encode
        print(f"  → Building function call...")
        contract_function = contract.functions[function_name](*converted_args)
        print(f"  ✓ Function call built")
        
        print(f"  → Encoding transaction data...")
        encoded_data = contract_function._encode_transaction_data()
        print(f"  ✓ Encoded successfully")
        print(f"    Data: {encoded_data[:66]}...")

        # Convert AVAX to WEI
        value_in_wei = w3.to_wei(value_in_avax, 'ether')
        print(f"  ✓ Value: {value_in_avax} AVAX = {value_in_wei} wei")

        # Construct transaction object
        tx_object = {
            "to": contract_address,
            "value": hex(value_in_wei),
            "data": encoded_data
        }
        
        print(f"\n  ✓✓✓ SUCCESS: Transaction generated ✓✓✓")
        print(f"    To: {tx_object['to']}")
        print(f"    Value: {tx_object['value']} ({value_in_avax} AVAX)")
        print(f"    Data: {encoded_data[:66]}... ({len(encoded_data)} chars)")
        print(f"{'='*60}\n")
        
        return json.dumps(tx_object)
        
    except Exception as e:
        error_msg = f"Failed to generate transaction: {str(e)}"
        print(f"\n  ✗✗✗ ERROR ✗✗✗")
        print(f"  {error_msg}")
        print(f"\n  Full traceback:")
        traceback.print_exc()
        print(f"{'='*60}\n")
        return json.dumps({"error": error_msg})