"""
Transaction Agent - Pure planning with automatic array fixing
"""

import time
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from tools import get_token_address, get_contract_abi
from tools import get_contract_abi_impl, generate_transaction_impl
from schemas import TransactionPlan
import os
from agent_config import config


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    iteration_count: int


# ✅ UNIVERSAL PROMPT - Works for ANY contract
PLANNING_PROMPT = """You are a transaction planning agent for Avalanche blockchain smart contracts.

**YOUR ONLY JOB:** Plan the transaction parameters for calling a function on a smart contract.

**Available Tools (for information gathering ONLY):**
- get_token_address: Get ERC20 token contract addresses (WAVAX, USDC, USDT, etc.)
- get_contract_abi: Get the contract's ABI to discover available functions and their signatures

**CRITICAL RULES:**
1. ✅ These tools help you gather information to PLAN the transaction
2. ✅ The function_name you return must be a SMART CONTRACT function (e.g., transfer, swap, approve, mint, purchase, claim)
3. ❌ NEVER put tool names (get_contract_abi, get_token_address) in function_name
4. ❌ If you don't know the exact function name, USE get_contract_abi to discover it first
5. ✅ If the user's message clearly states the function name, you can use it directly

**Common Function Patterns:**

**DEX/Swap Contracts:**
- swapExactAVAXForTokens, swapExactTokensForAVAX, swapExactTokensForTokens
- addLiquidity, removeLiquidity
- Args often include: amounts, token addresses, recipient, deadline

**Token Contracts (ERC20):**
- transfer(to, amount)
- approve(spender, amount)
- transferFrom(from, to, amount)

**NFT Contracts (ERC721/ERC1155):**
- mint(to, tokenId) or mint(amount)
- safeTransferFrom(from, to, tokenId)
- approve(to, tokenId)

**DeFi Protocols:**
- deposit(amount), withdraw(amount)
- stake(amount), unstake(amount)
- claim(), claimRewards()

**Insurance/Derivatives:**
- purchasePolicy(policyId), purchaseInsurance(insuranceId)
- claimPayout(claimId)
- cancelPolicy(policyId)

**Governance:**
- vote(proposalId, support)
- delegate(delegatee)
- propose(targets, values, calldatas, description)

**When User Says:**
- "swap 1 AVAX for USDC" → Use get_token_address, then plan swapExactAVAXForTokens
- "transfer 100 USDC to 0x123..." → Plan transfer(0x123..., 100000000) # Note: 6 decimals for USDC
- "approve contract 0xABC..." → Plan approve(0xABC..., amount)
- "call purchaseInsurance(25)" → Plan purchaseInsurance(25) # User gave you the function name
- "buy insurance 25" → Use get_contract_abi to find if it's purchaseInsurance, buyInsurance, or purchase
- "mint NFT" → Use get_contract_abi to find exact mint function signature

**Response Format:**
Return a TransactionPlan JSON with:
```json
{{
  "function_name": "actualContractFunction",
  "function_args": [arg1, arg2, ...],
  "value_in_avax": 0.0,
  "contract_address": "0x...",
  "reasoning": "Brief explanation"
}}
```

**Examples:**

1. **Token Transfer**
```json
{{
  "function_name": "transfer",
  "function_args": ["0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb5", 1000000000000000000],
  "value_in_avax": 0.0,
  "contract_address": "0xTokenAddress",
  "reasoning": "Transfer 1 token (18 decimals)"
}}
```

2. **DEX Swap**
```json
{{
  "function_name": "swapExactAVAXForTokens",
  "function_args": [0, ["0xWAVAX", "0xUSDC"], "0xUserAddress", 1699999999],
  "value_in_avax": 1.0,
  "contract_address": "0xRouterAddress",
  "reasoning": "Swap 1 AVAX for USDC"
}}
```

3. **Generic Contract Call** (when user provides function name)
```json
{{
  "function_name": "purchaseInsurance",
  "function_args": [25],
  "value_in_avax": 0.01,
  "contract_address": "{contract_address}",
  "reasoning": "Purchase insurance policy ID 25"
}}
```

**Your Context:**
- Contract: {contract_address}
- User: {user_address}
- Action: {action_description}

**If you're unsure about:**
- Token addresses → Use get_token_address
- Function names/signatures → Use get_contract_abi
- Decimal places → Check token ABI (usually 18 for most tokens, 6 for USDC)

**NOW PLAN THE TRANSACTION:**
"""


def fix_swap_arguments(function_name: str, args: list, abi_string: str) -> list:
    """
    Auto-fix common mistakes in argument structure.
    Handles common patterns where LLMs flatten arrays.
    """
    print(f"\n[AUTO-FIX] Checking arguments for {function_name}")
    print(f"  Input args: {args}")
    print(f"  Input types: {[type(a).__name__ for a in args]}")
    
    # ✅ UNIVERSAL: Parse ABI to find expected parameter structure
    import json
    try:
        abi = json.loads(abi_string)
    except:
        print("  ⚠️  Could not parse ABI, skipping auto-fix")
        return args
    
    # Find the function in ABI
    func_abi = None
    for item in abi:
        if item.get('type') == 'function' and item.get('name') == function_name:
            func_abi = item
            break
    
    if not func_abi:
        print(f"  ⚠️  Function '{function_name}' not found in ABI, skipping auto-fix")
        return args
    
    expected_inputs = func_abi.get('inputs', [])
    print(f"  Expected {len(expected_inputs)} parameters:")
    for i, inp in enumerate(expected_inputs):
        print(f"    [{i}] {inp.get('name', f'param{i}')}: {inp['type']}")
    
    # ✅ UNIVERSAL FIX: Check for flattened arrays
    if len(args) != len(expected_inputs):
        print(f"  ⚠️  Arg count mismatch: got {len(args)}, expected {len(expected_inputs)}")
        
        # Try to reconstruct arrays
        fixed_args = []
        arg_index = 0
        
        for i, expected in enumerate(expected_inputs):
            param_type = expected['type']
            
            # Check if this parameter should be an array
            if '[]' in param_type:
                print(f"  → Parameter {i} expects array: {param_type}")
                
                # Determine array size (heuristic: collect until next expected type or end)
                array_elements = []
                base_type = param_type.replace('[]', '')
                
                # Collect consecutive args that match the base type
                while arg_index < len(args):
                    current_arg = args[arg_index]
                    
                    # Check if this looks like the next parameter
                    if i + 1 < len(expected_inputs):
                        next_type = expected_inputs[i + 1]['type']
                        if self._matches_type(current_arg, next_type):
                            # This might be the next parameter, stop collecting
                            break
                    
                    # Add to array if it matches base type
                    if self._matches_type(current_arg, base_type):
                        array_elements.append(current_arg)
                        arg_index += 1
                    else:
                        break
                
                if array_elements:
                    print(f"    ✓ Reconstructed array with {len(array_elements)} elements")
                    fixed_args.append(array_elements)
                else:
                    print(f"    ✗ No elements found for array, using empty array")
                    fixed_args.append([])
            else:
                # Regular parameter
                if arg_index < len(args):
                    fixed_args.append(args[arg_index])
                    arg_index += 1
                else:
                    print(f"    ✗ Missing argument for parameter {i}")
                    return args  # Can't fix, return original
        
        if len(fixed_args) == len(expected_inputs):
            print(f"  ✓ Successfully fixed arguments!")
            print(f"  ✓ Fixed args: {fixed_args}")
            return fixed_args
        else:
            print(f"  ✗ Fix failed: got {len(fixed_args)} args, needed {len(expected_inputs)}")
            return args
    
    print(f"  ✓ Arguments already correct!")
    return args


def _matches_type(value, solidity_type: str) -> bool:
    """Helper to check if a Python value matches a Solidity type"""
    if solidity_type.startswith('uint') or solidity_type.startswith('int'):
        return isinstance(value, int)
    elif solidity_type == 'address':
        return isinstance(value, str) and value.startswith('0x') and len(value) == 42
    elif solidity_type == 'bool':
        return isinstance(value, bool)
    elif solidity_type == 'string':
        return isinstance(value, str)
    elif solidity_type == 'bytes' or solidity_type.startswith('bytes'):
        return isinstance(value, (str, bytes))
    return False


def create_planning_agent():
    """Creates agent for planning only with model selection"""
    
    tool_list = [get_token_address, get_contract_abi]
    
    # ✅ USE CONFIG: Create model using centralized config
    agent_name = "transaction_agent"
    model = config.create_model(agent_name, tools=tool_list, structured_output=TransactionPlan)
    
    tool_node = ToolNode(tool_list)
    
    def tool_node_with_logging(state):
        print("[PLANNING] Using tools...")
        result = tool_node.invoke(state)
        print("[PLANNING] Tools complete")
        return result
    
    def should_continue(state):
        iteration_limit = config.get_iteration_limit("transaction_agent")
        iteration_count = state.get('iteration_count', 0)
        
        if iteration_count > iteration_limit:
            return END
        
        last_message = state['messages'][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "call_tools"
        
        return END
    
    def call_model(state):
        current_count = state.get('iteration_count', 0)
        print(f"[PLANNING] Iteration {current_count + 1}")
        response = model.invoke(state['messages'])
        return {
            "messages": [response],
            "iteration_count": current_count + 1
        }
    
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("call_tools", tool_node_with_logging)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"call_tools": "call_tools", END: END}
    )
    workflow.add_edge('call_tools', 'agent')
    
    return workflow.compile()


def run_transaction_agent(
    message: str,
    user_address: str = None,
    contract_address: str = None
) -> dict:
    """
    Universal transaction planning with auto-fix:
    1. LLM plans (with tools)
    2. Auto-fix arguments based on ABI
    3. Python executes
    """
    
    print("\n" + "="*60)
    print("PHASE 1: PLANNING (LLM WITH TOOLS)")
    print("="*60)
    
    prompt = PLANNING_PROMPT.format(
        contract_address=contract_address or "Unknown",
        user_address=user_address or "Unknown",
        action_description=message
    )
    
    graph = create_planning_agent()
    
    try:
        result = graph.invoke({
            "messages": [HumanMessage(content=prompt)],
            "iteration_count": 0
        }, config={"recursion_limit": config.get_recursion_limit("transaction_agent")})
        
        print(f"\n[DEBUG] Result keys: {result.keys()}")
        print(f"[DEBUG] Number of messages: {len(result.get('messages', []))}")
        
        # Extract plan with better debugging
        plan = None
        for i, msg in enumerate(result.get('messages', [])):
            print(f"[DEBUG] Message {i}: type={type(msg).__name__}")
            
            if isinstance(msg, TransactionPlan):
                plan = msg
                print(f"[DEBUG] ✓ Found TransactionPlan at message {i}")
                break
            
            if hasattr(msg, 'content') and isinstance(msg.content, TransactionPlan):
                plan = msg.content
                print(f"[DEBUG] ✓ Found TransactionPlan in content at message {i}")
                break
            
            # Try to convert dict to TransactionPlan
            if hasattr(msg, 'content') and isinstance(msg.content, dict):
                try:
                    plan = TransactionPlan(**msg.content)
                    print(f"[DEBUG] ✓ Converted dict to TransactionPlan at message {i}")
                    break
                except Exception as e:
                    print(f"[DEBUG] ✗ Failed to convert dict: {e}")
        
        if not plan:
            print(f"\n[ERROR] No TransactionPlan found in {len(result.get('messages', []))} messages")
            return {
                "type": "error", 
                "message": "Transaction planning failed - the AI couldn't understand the function to call. Try being more specific about the function name."
            }
        
        print(f"\n[PLAN RECEIVED]")
        print(f"  Function: {plan.function_name}")
        print(f"  Args: {plan.function_args}")
        print(f"  Args types: {[type(arg).__name__ for arg in plan.function_args]}")
        print(f"  Value: {plan.value_in_avax} AVAX")
        
        # Get ABI for auto-fix
        print("\n[PHASE 1.5: AUTO-FIX CHECK]")
        abi = get_contract_abi_impl(plan.contract_address)
        if abi.startswith("Error"):
            return {"type": "error", "message": f"Failed to get ABI: {abi}"}
        
        # Auto-fix arguments based on ABI
        fixed_args = fix_swap_arguments(
            plan.function_name,
            plan.function_args,
            abi
        )
        
        plan.function_args = fixed_args
        
        print("\n" + "="*60)
        print("PHASE 2: EXECUTION (PYTHON ONLY)")
        print("="*60)
        
        print("[EXECUTION] Generating transaction...")
        result = generate_transaction_impl(
            contract_address=plan.contract_address,
            abi=abi,
            function_name=plan.function_name,
            function_args=fixed_args,
            value_in_avax=plan.value_in_avax
        )
        
        if not result["success"]:
            return {"type": "error", "message": result["error"]}
        
        tx = result["transaction"]
        
        # Verify
        data_length = len(tx["data"])
        if data_length < 50:
            return {"type": "error", "message": "Transaction data too short - function call may be invalid"}
        
        print(f"\n[SUCCESS] Transaction ready")
        print(f"  ✓ To: {tx['to']}")
        print(f"  ✓ Value: {tx['value']}")
        print(f"  ✓ Data: {tx['data'][:66]}... ({data_length} chars)")
        print("="*60 + "\n")
        
        return {
            "type": "transaction",
            "transaction": tx,
            "message": plan.reasoning
        }
        
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {"type": "error", "message": f"Transaction failed: {str(e)}"}


# Add helper to the class
def fix_swap_arguments(function_name: str, args: list, abi_string: str) -> list:
    """Auto-fix with ABI-aware array reconstruction"""
    print(f"\n[AUTO-FIX] Checking arguments for {function_name}")
    print(f"  Input args: {args}")
    print(f"  Input types: {[type(a).__name__ for a in args]}")
    
    import json
    try:
        abi = json.loads(abi_string)
    except:
        print("  ⚠️  Could not parse ABI, skipping auto-fix")
        return args
    
    # Find function in ABI
    func_abi = None
    for item in abi:
        if item.get('type') == 'function' and item.get('name') == function_name:
            func_abi = item
            break
    
    if not func_abi:
        print(f"  ⚠️  Function '{function_name}' not found in ABI")
        return args
    
    expected_inputs = func_abi.get('inputs', [])
    print(f"  Expected {len(expected_inputs)} parameters")
    
    # If counts match, assume it's correct
    if len(args) == len(expected_inputs):
        print(f"  ✓ Argument count matches, assuming correct")
        return args
    
    # Try to fix flattened arrays
    print(f"  ⚠️  Count mismatch: {len(args)} args vs {len(expected_inputs)} expected")
    print(f"  → Attempting to reconstruct arrays...")
    
    fixed_args = []
    arg_idx = 0
    
    for i, param in enumerate(expected_inputs):
        param_type = param['type']
        
        if '[]' in param_type:
            # Collect elements for array
            array_items = []
            
            # Simple heuristic: collect until we hit different type or run out
            while arg_idx < len(args):
                # If this is the last parameter, take remaining args
                if i == len(expected_inputs) - 1:
                    array_items.append(args[arg_idx])
                    arg_idx += 1
                # Otherwise, collect until count matches remaining params
                elif len(fixed_args) + 1 + (len(args) - arg_idx) >= len(expected_inputs):
                    array_items.append(args[arg_idx])
                    arg_idx += 1
                else:
                    break
            
            fixed_args.append(array_items)
            print(f"    ✓ Reconstructed array[{i}] with {len(array_items)} items")
        else:
            # Regular parameter
            if arg_idx < len(args):
                fixed_args.append(args[arg_idx])
                arg_idx += 1
    
    if len(fixed_args) == len(expected_inputs):
        print(f"  ✓ Successfully reconstructed {len(fixed_args)} parameters")
        return fixed_args
    
    print(f"  ✗ Reconstruction failed, using original args")
    return args