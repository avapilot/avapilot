import re
import time
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
    return FUJI_TOKEN_ADDRESSES.get(token_symbol.upper(), "Error: Token not found.")

@tool
def get_contract_abi(contract_address: str) -> str:
    """
    Fetches the ABI (Application Binary Interface) for a given smart 
    contract address on the Avalanche C-Chain. The ABI defines the
    contract's functions and is its technical schema.
    
    This uses the free tier of Snowtrace API which allows 2 requests/second
    and 10,000 calls per day without requiring a real API key.
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
            return data["result"]
        else:
            return f"Error fetching ABI: {data['message']} - {data['result']}"
    except requests.exceptions.RequestException as e:
        return f"Error: Network request failed: {e}"
    except json.JSONDecodeError:
        return "Error: Failed to parse response from block explorer."

@tool
def generate_transaction(
    contract_address: str, 
    abi: str, 
    function_name: str, 
    args: list,
    value_in_avax: float = 0.0
) -> str:
    """
    Generates an unsigned transaction object. Use this ONLY after you have the ABI.
    
    IMPORTANT: You MUST analyze the ABI to determine:
    1. The correct function name (e.g., "swapExactAVAXForTokens")
    2. The exact parameter types and order
    3. How to construct each argument
    
    Args:
        contract_address: The address of the smart contract.
        abi: The JSON string of the contract's ABI.
        function_name: The exact name of the function to call (must match ABI).
        args: A list of arguments for the function, in the correct order and format.
        value_in_avax: The amount of AVAX to send with the transaction (for payable functions).
    
    Returns a JSON string of the transaction object with 'to', 'value', and 'data' fields.
    """
    print(f"---TOOL CALLED: generate_transaction for function: {function_name}---")
    print(f"  Contract: {contract_address}")
    print(f"  Value: {value_in_avax} AVAX")
    print(f"  Args: {args}")
    
    try:
        w3 = Web3()
        contract_abi = json.loads(abi)
        contract = w3.eth.contract(address=contract_address, abi=contract_abi)

        # Encode the function call
        encoded_data = contract.encodeABI(fn_name=function_name, args=args)

        # Convert AVAX to WEI for the 'value' field
        value_in_wei = w3.to_wei(value_in_avax, 'ether')

        # Construct the transaction object
        tx_object = {
            "to": contract_address,
            "value": hex(value_in_wei),
            "data": encoded_data
        }
        
        # Return as JSON string for LLM to parse
        result = json.dumps(tx_object)
        print(f"  SUCCESS: Generated transaction: {result}")
        return result
        
    except Exception as e:
        error_msg = f"Failed to generate transaction: {str(e)}"
        print(f"  ERROR: {error_msg}")
        return json.dumps({"error": error_msg})