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
from contract_analyzer import identify_contract_type, explain_contract
from network_config import (
    RPC_URL, EXPLORER_API_URL, EXPLORER_API_KEY, TOKEN_ADDRESSES, NETWORK_NAME,
)


# ============================================
# IMPLEMENTATION FUNCTIONS (No @tool decorator)
# ============================================

def get_token_address_impl(token_symbol: str) -> str:
    """Implementation that can be called from Python directly"""
    address = TOKEN_ADDRESSES.get(token_symbol.upper(), "Error: Token not found.")
    print(f"  [IMPL] get_token_address({token_symbol}) → {address}")
    return address


def get_contract_abi_impl(contract_address: str) -> str:
    """Implementation that can be called from Python directly"""
    print(f"  [IMPL] get_contract_abi({contract_address})")
    
    params = {
        "module": "contract",
        "action": "getabi",
        "address": contract_address,
        "apikey": EXPLORER_API_KEY
    }

    try:
        response = requests.get(EXPLORER_API_URL, params=params)
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


@tool
def read_contract_function(
    contract_address: str,
    function_name: str,
    function_args: list
) -> str:
    """
    Reads data from a smart contract (view/pure functions only).
    
    **SUPPORTS ALL RETURN TYPES:** This tool successfully handles:
    - Simple types (uint256, address, bool, string)
    - Arrays (uint256[], address[], bytes32[], etc.)
    - Tuples and complex structs
    - Nested data structures
    
    Common use cases:
    - Check token balance: read_contract_function("0xUSDC...", "balanceOf", ["0xUserAddr..."])
    - Get all contracts: read_contract_function("0xContract...", "getAllContracts", [])
    - Get array of IDs: read_contract_function("0xContract...", "getAllIds", [])
    
    Args:
        contract_address: Contract to read from
        function_name: Function to call (must be view/pure)
        function_args: Arguments as list (use [] for functions with no arguments)
        
    Returns:
        JSON string with {"success": true, "result": "..."} or {"success": false, "error": "..."}
        Result can be any type including arrays and will be properly serialized.
    """

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
    Finds the contract address for a given token symbol on the current network.
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



@tool
def analyze_contract(contract_address: str) -> str:
    """
    Deeply analyzes a smart contract using a dedicated analysis agent.
    
    Handles large contracts automatically through:
    - Smart chunking of source code
    - Iterative analysis with specialized tools
    - Focused examination of critical functions
    - Comprehensive security assessment
    
    Use this when user asks:
    - "What does contract X do?"
    - "How does contract X work?"
    - "Analyze contract X"
    - "What are the risks of contract X?"
    - "Is contract X safe?"
    
    Args:
        contract_address: The contract address to analyze
        
    Returns:
        Comprehensive analysis report with security assessment
    """
    from contract_analysis_agent import run_contract_analysis
    
    print(f"[TOOL] analyze_contract called: {contract_address}")
    
    # Get ABI
    abi_json = get_contract_abi_impl(contract_address)
    
    if abi_json.startswith("Error"):
        return f"Could not analyze contract: {abi_json}"
    
    try:
        abi = json.loads(abi_json)
        
        # Quick type identification for header
        analysis = identify_contract_type(abi)
        functions = [item['name'] for item in abi if item.get('type') == 'function']
        
        # Try to get source code
        print("[ANALYZE] Attempting to retrieve source code...")
        source_code = get_source_code_impl(contract_address)
        
        has_source = source_code and not source_code.startswith("Error")
        verification_badge = "✅ VERIFIED" if has_source else "⚠️ UNVERIFIED"
        
        if has_source:
            print(f"[ANALYZE] ✅ Source code found ({len(source_code)} chars)")
        else:
            print(f"[ANALYZE] ⚠️ No source code available")
            source_code = None
        
        # Run dedicated analysis agent
        print("[ANALYZE] Launching contract analysis agent...")
        analysis_report = run_contract_analysis(
            contract_address=contract_address,
            abi=abi,
            source_code=source_code
        )
        
        # Build final response with header
        result = f"""**🔍 Deep Contract Analysis**

**Contract:** `{contract_address}`
**Status:** {verification_badge}
**Classification:** {analysis['type'].replace('_', ' ').title()} (Confidence: {int(analysis['confidence']*100)}%)
**Total Functions:** {len(functions)}
**Analysis Method:** {'Source Code Review' if has_source else 'ABI-Based Inference'}

---

{analysis_report}

---

*Analysis generated by specialized contract analysis agent.*
*{'' if has_source else '⚠️ Source code not verified - analysis based on function signatures only.'}*
*Always verify and test with small amounts first.*"""
        
        return result
        
    except Exception as e:
        error_msg = f"Error analyzing contract: {str(e)}"
        print(f"[ANALYZE ERROR] {error_msg}")
        import traceback
        traceback.print_exc()
        return error_msg


def get_source_code_impl(contract_address: str) -> str:
    """
    Fetches verified source code from block explorer
    """
    print(f"  [IMPL] get_source_code({contract_address})")
    
    params = {
        "module": "contract",
        "action": "getsourcecode",
        "address": contract_address,
        "apikey": EXPLORER_API_KEY
    }
    
    try:
        response = requests.get(EXPLORER_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data["status"] == "1" and data["result"]:
            result = data["result"][0]
            source_code = result.get("SourceCode", "")
            
            if source_code:
                # Handle JSON-wrapped source
                if source_code.startswith("{"):
                    try:
                        source_json = json.loads(source_code)
                        if "sources" in source_json:
                            all_sources = []
                            for filename, content in source_json["sources"].items():
                                all_sources.append(f"// File: {filename}\n{content.get('content', '')}")
                            source_code = "\n\n".join(all_sources)
                    except:
                        pass
                
                print(f"  [IMPL] ✅ Source code retrieved ({len(source_code)} chars)")
                return source_code
            else:
                error = "Error: Contract source code not verified"
                print(f"  [IMPL] ⚠️ {error}")
                return error
        else:
            error = f"Error fetching source: {data.get('message', 'Unknown error')}"
            print(f"  [IMPL] ❌ {error}")
            return error
            
    except Exception as e:
        error = f"Error: {str(e)}"
        print(f"  [IMPL] ❌ {error}")
        return error


def read_contract_function_impl(
    contract_address: str,
    function_name: str,
    function_args: list
) -> dict:
    """
    Implementation for reading contract state (view/pure functions only).
    """
    print(f"\n{'='*60}")
    print(f"[READ] {function_name} on {contract_address}")
    print(f"{'='*60}")
    print(f"  Args: {function_args}")
    print(f"  Args type: {type(function_args)}")
    print(f"  Args length: {len(function_args)}")
    
    try:
        # Connect to RPC
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not w3.is_connected():
            error = "RPC connection failed"
            print(f"  ✗ {error}")
            return {"success": False, "error": error}
        
        print(f"  ✓ Connected to {NETWORK_NAME}")
        
        # Get ABI
        abi = get_contract_abi_impl(contract_address)
        if abi.startswith("Error"):
            print(f"  ✗ ABI fetch failed: {abi}")
            return {"success": False, "error": abi}
        
        contract_abi = json.loads(abi)
        print(f"  ✓ ABI loaded, {len(contract_abi)} items")
        
        # Find function in ABI
        function_abi = None
        for item in contract_abi:
            if item.get('name') == function_name and item.get('type') == 'function':
                function_abi = item
                break
        
        if not function_abi:
            error = f"Function '{function_name}' not found in contract ABI"
            print(f"  ✗ {error}")
            return {"success": False, "error": error}
        
        print(f"  ✓ Function found in ABI")
        print(f"    Inputs: {function_abi.get('inputs', [])}")
        print(f"    Outputs: {function_abi.get('outputs', [])}")
        
        # Convert arguments
        converted_args = []
        for i, (arg, param) in enumerate(zip(function_args, function_abi.get('inputs', []))):
            param_type = param.get('type', 'unknown')
            print(f"    Converting arg {i}: {arg} ({type(arg).__name__}) → {param_type}")
            
            if param_type.startswith('uint') or param_type.startswith('int'):
                converted = int(float(arg)) if isinstance(arg, (str, float)) else arg
            elif param_type == 'address':
                converted = Web3.to_checksum_address(arg.lower()) if isinstance(arg, str) else arg
            elif param_type == 'bool':
                converted = bool(arg) if not isinstance(arg, str) else arg.lower() in ['true', '1', 'yes']
            else:
                converted = arg
            
            converted_args.append(converted)
            print(f"      → {converted}")
        
        print(f"  ✓ Arguments converted: {converted_args}")
        
        # Create contract instance
        contract_address_checksum = Web3.to_checksum_address(contract_address.lower())
        contract = w3.eth.contract(address=contract_address_checksum, abi=contract_abi)
        print(f"  ✓ Contract instance created")
        
        # Call function
        print(f"  → Calling contract.functions.{function_name}({converted_args})...")
        contract_function = contract.functions[function_name](*converted_args)
        result = contract_function.call()
        
        print(f"  ✓✓✓ SUCCESS")
        print(f"    Result type: {type(result).__name__}")
        print(f"    Result value: {result}")
        
        # ✅ NEW: Label the results using ABI output names
        outputs = function_abi.get('outputs', [])
        
        if isinstance(result, (list, tuple)) and len(outputs) > 1:
            # Multiple return values - create labeled dictionary
            labeled_result = {}
            for i, (value, output_spec) in enumerate(zip(result, outputs)):
                field_name = output_spec.get('name', f'output_{i}')
                field_type = output_spec.get('type', 'unknown')
                
                # Convert to string for serialization
                str_value = str(value)
                labeled_result[field_name] = {
                    "value": str_value,
                    "type": field_type
                }
                
                # Add Wei conversion hint for large uint256 values
                if field_type.startswith('uint') and isinstance(value, int) and value > 1000000000000000:
                    labeled_result[field_name]["wei_hint"] = "⚠️ Large number - likely Wei. Call convert_wei_to_avax()"
            
            print(f"    Labeled result: {labeled_result}")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "result": labeled_result,
                "raw_values": [str(v) for v in result],
                "abi_outputs": outputs
            }
        else:
            # Single return value
            serialized = str(result)
            
            response = {"success": True, "result": serialized}
            
            # Add hint for likely Wei values
            if isinstance(result, int) and result > 1000000000000000:
                response["conversion_hint"] = "⚠️ Large number detected. Call convert_wei_to_avax() if this represents AVAX!"
            
            print(f"    Serialized result: {serialized}")
            print(f"{'='*60}\n")
            
            return response
        
    except Exception as e:
        error_msg = f"Error reading contract: {str(e)}"
        print(f"  ✗✗✗ ERROR: {error_msg}")
        traceback.print_exc()
        print(f"{'='*60}\n")
        return {"success": False, "error": error_msg}


@tool
def convert_wei_to_avax(wei_value: str) -> str:
    """
    Converts Wei (smallest unit) to AVAX (human-readable)
    
    Args:
        wei_value: Amount in Wei as string (e.g., "11000000000000000000")
    
    Returns:
        JSON string with conversion result
        
    Example:
        >>> convert_wei_to_avax("11000000000000000000")
        '{"wei": "11000000000000000000", "avax": "11.0", "formatted": "11 AVAX"}'
    """
    try:
        wei = int(wei_value)
        avax = wei / 1e18
        
        # Format nicely
        if avax >= 1:
            formatted = f"{avax:.2f} AVAX"
        elif avax >= 0.0001:
            formatted = f"{avax:.6f} AVAX"
        else:
            formatted = f"{avax:.10f} AVAX"
        
        result = {
            "success": True,
            "wei": wei_value,
            "avax": str(avax),
            "formatted": formatted
        }
        
        print(f"[WEI→AVAX] {wei_value} Wei = {formatted}")
        return json.dumps(result)
        
    except Exception as e:
        error_result = {
            "success": False,
            "error": str(e),
            "wei": wei_value
        }
        print(f"[WEI→AVAX ERROR] {e}")
        return json.dumps(error_result)


@tool
def get_insurance_details(contract_address: str, insurance_id: int) -> str:
    """
    Gets human-readable details for a specific insurance contract.
    Automatically handles Wei conversion and proper field interpretation.
    
    Args:
        contract_address: Insurance contract address
        insurance_id: Insurance ID number
        
    Returns:
        JSON with formatted insurance details
    """
    print(f"[INSURANCE] Getting details for insurance #{insurance_id}")
    
    # Get raw data
    result = read_contract_function_impl(contract_address, "insurances", [insurance_id])
    
    if not result.get('success'):
        return json.dumps({"error": result.get('error', 'Failed to read contract')})
    
    raw_data = result.get('result', {})
    
    # Parse insurance data with proper field understanding
    try:
        # Get labeled fields
        trigger_price_wei = raw_data.get('triggerPrice', {}).get('value', '0')
        reserve_amount_wei = raw_data.get('reserveAmount', {}).get('value', '0')
        insurance_fee_wei = raw_data.get('insuranceFee', {}).get('value', '0')
        
        # Convert Wei to AVAX for AVAX amounts
        reserve_avax = int(reserve_amount_wei) / 1e18
        fee_avax = int(insurance_fee_wei) / 1e18
        
        # triggerPrice might be in USD (scaled) - check if it makes sense
        trigger_value = int(trigger_price_wei)
        if trigger_value > 1e15:  # If > 0.001 AVAX worth, probably USD scaled
            trigger_usd = trigger_value / 1e18
            trigger_display = f"${trigger_usd:.2f} USD"
        else:
            trigger_display = f"{trigger_value} (raw value)"
        
        insurance_details = {
            "insurance_id": insurance_id,
            "trigger_condition": trigger_display,
            "payout_amount": f"{reserve_avax:.6f} AVAX",
            "premium_cost": f"{fee_avax:.6f} AVAX",
            "seller": raw_data.get('seller', {}).get('value', 'N/A'),
            "buyer": raw_data.get('buyer', {}).get('value', 'N/A'),
            "active": raw_data.get('active', {}).get('value', False),
            "triggered": raw_data.get('triggered', {}).get('value', False),
            "summary": f"Pays {reserve_avax:.6f} AVAX if price reaches {trigger_display}. Premium: {fee_avax:.6f} AVAX"
        }
        
        print(f"[INSURANCE] ✓ Parsed: {insurance_details['summary']}")
        return json.dumps(insurance_details, indent=2)
        
    except Exception as e:
        print(f"[INSURANCE] Parse error: {e}")
        return json.dumps({
            "error": f"Failed to parse insurance data: {e}",
            "raw_data": raw_data
        })


@tool
def explore_contract_state(contract_address: str, sample_ids: list = None) -> str:
    """
    Automatically discovers and reads contract state, including:
    - Zero-parameter view functions (owner, totalSupply, etc.)
    - Single-parameter getters with sample IDs (insurances(26), stakes(0), etc.)
    
    Use this to explore what data is stored in a contract.
    
    Args:
        contract_address: Contract to explore
        sample_ids: Optional list of IDs to try (e.g., [0, 1, 26] for insurances)
        
    Returns:
        JSON with discovered state and available getters
        
    Example:
        explore_contract_state("0xABC...", [26, 27]) 
        → Tries insurances(26), insurances(27), stakes(26), etc.
    """
    print(f"[EXPLORE] Discovering state for {contract_address}")
    if sample_ids:
        print(f"[EXPLORE] Will try IDs: {sample_ids}")
    
    # Get ABI
    abi_json = get_contract_abi_impl(contract_address)
    if abi_json.startswith("Error"):
        return json.dumps({"error": abi_json})
    
    abi = json.loads(abi_json)
    
    # Categorize functions
    zero_param_funcs = []
    single_uint_funcs = []  # Likely mapping getters
    single_address_funcs = []  # Likely user-specific data
    
    for item in abi:
        if item.get('type') != 'function':
            continue
        if item.get('stateMutability') not in ['view', 'pure']:
            continue
            
        inputs = item.get('inputs', [])
        func_name = item['name']
        
        if len(inputs) == 0:
            zero_param_funcs.append(func_name)
        elif len(inputs) == 1:
            param_type = inputs[0]['type']
            if param_type.startswith('uint'):
                single_uint_funcs.append(func_name)
            elif param_type == 'address':
                single_address_funcs.append(func_name)
    
    print(f"[EXPLORE] Found:")
    print(f"  - {len(zero_param_funcs)} zero-param functions")
    print(f"  - {len(single_uint_funcs)} uint-param functions (likely mappings)")
    print(f"  - {len(single_address_funcs)} address-param functions")
    
    results = {
        "contract": contract_address,
        "zero_param_state": {},
        "id_based_getters": {},
        "available_getters": {
            "by_id": single_uint_funcs,
            "by_address": single_address_funcs
        }
    }
    
    # 1. Call zero-parameter functions
    for func_name in zero_param_funcs[:10]:  # Limit to avoid spam
        try:
            result = read_contract_function_impl(contract_address, func_name, [])
            if result['success']:
                results["zero_param_state"][func_name] = result['result']
        except Exception as e:
            print(f"[EXPLORE] {func_name}() failed: {e}")
            continue
    
    # 2. If sample IDs provided, try single-uint functions
    if sample_ids and single_uint_funcs:
        print(f"[EXPLORE] Testing {len(single_uint_funcs)} getters with IDs {sample_ids}")
        
        for func_name in single_uint_funcs[:5]:  # Limit functions tested
            results["id_based_getters"][func_name] = {}
            
            for id_val in sample_ids[:3]:  # Limit IDs tested per function
                try:
                    result = read_contract_function_impl(
                        contract_address, 
                        func_name, 
                        [id_val]
                    )
                    if result['success']:
                        results["id_based_getters"][func_name][str(id_val)] = result['result']
                        print(f"[EXPLORE] ✓ {func_name}({id_val}) = {result['result']}")
                except Exception as e:
                    print(f"[EXPLORE] {func_name}({id_val}) failed: {e}")
                    continue
    
    # 3. Add usage hints
    results["usage_hints"] = {
        "to_query_specific_id": f"Use read_contract_function('{contract_address}', 'FUNCTION_NAME', [ID])",
        "available_id_getters": single_uint_funcs[:10],
        "example": f"read_contract_function('{contract_address}', '{single_uint_funcs[0]}', [26])" if single_uint_funcs else "No ID-based getters found"
    }
    
    return json.dumps(results, indent=2)

@tool
def get_item_by_id(
    contract_address: str, 
    item_name: str, 
    item_id: int
) -> str:
    """
    Intelligently retrieves a specific item from a contract by trying common getter patterns.
    
    Automatically tries multiple naming conventions:
    - insurances(26), insurance(26), insuranceList(26), getInsurance(26)
    - stakes(5), stake(5), stakeList(5), getStake(5)
    
    Use this when user asks for a specific item by ID/index.
    
    Args:
        contract_address: Contract to query
        item_name: Base name (e.g., "insurance", "stake", "contract")
        item_id: The ID/index to retrieve
        
    Returns:
        JSON with item data or list of attempted functions
        
    Example:
        get_item_by_id("0xABC...", "insurance", 26)
        → Tries insurances(26), insurance(26), etc.
    """
    print(f"[GET_BY_ID] Searching for {item_name} #{item_id} in {contract_address}")
    
    # Generate variations
    base = item_name.lower().rstrip('s')  # Remove trailing 's' if present
    variations = [
        f"{base}s",           # insurances
        base,                 # insurance  
        f"{base}List",        # insuranceList
        f"get{base.capitalize()}",      # getInsurance
        f"get{base.capitalize()}s",     # getInsurances
        f"{base}Info",        # insuranceInfo
        f"{base}Data",        # insuranceData
    ]
    
    print(f"[GET_BY_ID] Will try: {variations}")
    
    # Get ABI to check which functions exist
    abi_json = get_contract_abi_impl(contract_address)
    if abi_json.startswith("Error"):
        return json.dumps({"error": abi_json})
    
    abi = json.loads(abi_json)
    available_funcs = [
        item['name'] for item in abi 
        if item.get('type') == 'function' 
        and item.get('stateMutability') in ['view', 'pure']
        and len(item.get('inputs', [])) == 1
        and item['inputs'][0]['type'].startswith('uint')
    ]
    
    print(f"[GET_BY_ID] Available single-uint functions: {available_funcs}")
    
    # Try each variation
    for func_name in variations:
        if func_name not in available_funcs:
            continue
            
        print(f"[GET_BY_ID] Trying {func_name}({item_id})...")
        
        try:
            result = read_contract_function_impl(
                contract_address,
                func_name,
                [item_id]
            )
            
            if result['success']:
                print(f"[GET_BY_ID] ✅ SUCCESS with {func_name}!")
                return json.dumps({
                    "success": True,
                    "function_used": func_name,
                    "id": item_id,
                    "data": result['result']
                }, indent=2)
        except Exception as e:
            print(f"[GET_BY_ID] {func_name} failed: {e}")
            continue

    return json.dumps({"error": f"No matching function found for item type '{item_type}' with ID {item_id}"})


# ============================================
# TRANSACTION HISTORY
# ============================================

def get_transaction_history_impl(address: str, count: int = 10) -> list:
    """Fetch last N transactions for an address from the block explorer."""
    print(f"[TX_HISTORY] Fetching last {count} txs for {address}")

    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "page": 1,
        "offset": count,
        "sort": "desc",
        "apikey": EXPLORER_API_KEY,
    }

    try:
        resp = requests.get(EXPLORER_API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "1":
            return [{"error": data.get("message", "No transactions found")}]

        txs = []
        for tx in data.get("result", [])[:count]:
            value_wei = int(tx.get("value", "0"))
            value_avax = value_wei / 1e18

            txs.append({
                "hash": tx["hash"],
                "from": tx["from"],
                "to": tx.get("to", "contract creation"),
                "value_avax": f"{value_avax:.6f}",
                "function": tx.get("functionName", "").split("(")[0] or "transfer",
                "status": "success" if tx.get("isError") == "0" else "failed",
                "timestamp": tx.get("timeStamp"),
            })

        print(f"[TX_HISTORY] Found {len(txs)} transactions")
        return txs

    except Exception as e:
        print(f"[TX_HISTORY] Error: {e}")
        return [{"error": str(e)}]


@tool
def get_transaction_history(address: str, count: int = 10) -> str:
    """
    Gets the last N transactions for a wallet or contract address.

    Use when user asks:
    - "Show my recent transactions"
    - "What happened on this contract recently?"
    - "Show last 5 transactions for 0x..."

    Args:
        address: Wallet or contract address
        count: Number of transactions to return (default 10, max 50)

    Returns:
        JSON with list of transactions (hash, from, to, value, function, status)
    """
    count = min(count, 50)
    txs = get_transaction_history_impl(address, count)
    return json.dumps(txs, indent=2)