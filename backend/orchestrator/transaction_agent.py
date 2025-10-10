"""
Transaction Agent - Pure planning with automatic array fixing
"""

import time
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_google_vertexai import ChatVertexAI
from tools import get_token_address, get_contract_abi
from tools import get_contract_abi_impl, generate_transaction_impl
from schemas import TransactionPlan


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    iteration_count: int


# Even more aggressive prompting
PLANNING_PROMPT = """You are a blockchain transaction planner for Avalanche.

**YOUR TASK:** Create a precise transaction plan.

**CRITICAL: Understanding address[] Parameters**

When you see `address[] path` in a function signature, you MUST create a Python LIST:

✅ CORRECT FORMAT:
function_args: [1, ["0xAddr1", "0xAddr2"], "0xUserAddr", 1760107642]
                   ↑↑↑ This is a LIST with square brackets containing 2 addresses ↑↑↑

❌ WRONG FORMAT (DON'T DO THIS):
function_args: [1, "0xAddr1", "0xAddr2", "0xUserAddr", 1760107642]
                   ↑ These are separate strings, NOT a list!

**STEP-BY-STEP for swapExactAVAXForTokens:**

1. Check function signature:
   ```
   swapExactAVAXForTokens(
     uint256 amountOutMin,    ← Argument 0: integer
     address[] path,          ← Argument 1: ARRAY (list with [])
     address to,              ← Argument 2: string
     uint256 deadline         ← Argument 3: integer
   )
   ```

2. For "swap AVAX for USDC":
   - amountOutMin = 1 (integer)
   - path = [WAVAX_address, USDC_address] ← MUST BE IN []!
   - to = user_wallet_address
   - deadline = {timestamp} + 1200

3. Build function_args with exactly 4 arguments:
   ```python
   [
     1,                                                    # arg 0
     ["0x1d308089a2d1ced3f1ce36b1fcaf815b07217be3",     # arg 1 (list!)
      "0x5425890298aed601595a70AB815c96711a31Bc65"],
     "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",      # arg 2
     {deadline}                                           # arg 3
   ]
   ```

**EXAMPLE OUTPUT:**
{{
  "function_name": "swapExactAVAXForTokens",
  "function_args": [
    1,
    ["0x1d308089a2d1ced3f1ce36b1fcaf815b07217be3", "0x5425890298aed601595a70AB815c96711a31Bc65"],
    "0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
    {deadline}
  ],
  "value_in_avax": 0.01,
  "contract_address": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4",
  "reasoning": "Swap 0.01 AVAX for USDC"
}}

**PROCESS:**
1. Call get_token_address("WAVAX") → get address
2. Call get_token_address("USDC") → get address
3. Call get_contract_abi(contract) → verify function exists
4. Return plan with path as [WAVAX_address, USDC_address] in a list!

Current timestamp: {timestamp}
"""


def fix_swap_arguments(function_name: str, args: list, abi_string: str) -> list:
    """
    Auto-fix common mistakes in argument structure.
    If LLM flattens the address[] array, reconstruct it.
    """
    print(f"\n[AUTO-FIX] Checking arguments for {function_name}")
    print(f"  Input args: {args}")
    print(f"  Input types: {[type(a).__name__ for a in args]}")
    
    if function_name != "swapExactAVAXForTokens":
        print(f"  → Not a swap function, no fix needed")
        return args
    
    # Expected: [amountOutMin, [path], to, deadline]
    # If we have 5+ args, LLM likely flattened the array
    if len(args) == 4:
        # Check if arg[1] is already a list
        if isinstance(args[1], list):
            print(f"  ✓ Arguments already correct!")
            return args
        else:
            print(f"  ⚠️  Arg[1] should be list but is {type(args[1]).__name__}")
            # Maybe it's a single-element path?
            print(f"  → Cannot auto-fix: unknown structure")
            return args
    
    elif len(args) == 5:
        # Likely: [amountOutMin, addr1, addr2, to, deadline]
        # Fix: [amountOutMin, [addr1, addr2], to, deadline]
        print(f"  ⚠️  Detected flattened array (5 args instead of 4)")
        print(f"  → Reconstructing: args[1] and args[2] should be in a list")
        
        fixed_args = [
            args[0],           # amountOutMin
            [args[1], args[2]], # [path]
            args[3],           # to
            args[4]            # deadline
        ]
        
        print(f"  ✓ Fixed args: {fixed_args}")
        print(f"  ✓ Fixed types: {[type(a).__name__ for a in fixed_args]}")
        return fixed_args
    
    else:
        print(f"  ⚠️  Unexpected arg count: {len(args)}")
        print(f"  → Cannot auto-fix")
        return args


def create_planning_agent():
    """Creates agent for planning only"""
    
    tool_list = [get_token_address, get_contract_abi]
    
    model = ChatVertexAI(
        model="gemini-2.0-flash",
        location="global",
        project="avapilot"
    ).bind_tools(tool_list).with_structured_output(TransactionPlan)
    
    tool_node = ToolNode(tool_list)
    
    def tool_node_with_logging(state):
        print("[PLANNING] Using tools...")
        result = tool_node.invoke(state)
        print("[PLANNING] Tools complete")
        return result
    
    def should_continue(state):
        iteration_count = state.get('iteration_count', 0)
        if iteration_count > 5:
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
    Two phases with auto-fix:
    1. LLM plans (with tools)
    2. Auto-fix arguments if needed
    3. Python executes (no LLM)
    """
    
    print("\n" + "="*60)
    print("PHASE 1: PLANNING (LLM WITH TOOLS)")
    print("="*60)
    
    current_timestamp = int(time.time())
    deadline = current_timestamp + 1200
    
    prompt = PLANNING_PROMPT.format(
        timestamp=current_timestamp,
        deadline=deadline
    )
    
    full_message = f"{prompt}\n\n**Task:** {message}"
    if user_address:
        full_message += f"\n**User:** {user_address}"
    if contract_address:
        full_message += f"\n**Contract:** {contract_address}"
    
    graph = create_planning_agent()
    
    try:
        result = graph.invoke({
            "messages": [HumanMessage(content=full_message)],
            "iteration_count": 0
        })
        
        # Extract plan
        plan = None
        for msg in result.get('messages', []):
            if isinstance(msg, TransactionPlan):
                plan = msg
                break
        
        if not plan:
            return {"type": "error", "message": "Planning failed"}
        
        print(f"\n[PLAN RECEIVED]")
        print(f"  Function: {plan.function_name}")
        print(f"  Args: {plan.function_args}")
        print(f"  Args types: {[type(arg).__name__ for arg in plan.function_args]}")
        print(f"  Args count: {len(plan.function_args)}")
        
        # Get ABI first for auto-fix
        print("\n[PHASE 1.5: AUTO-FIX CHECK]")
        abi = get_contract_abi_impl(plan.contract_address)
        if abi.startswith("Error"):
            return {"type": "error", "message": f"Failed to get ABI: {abi}"}
        
        # Auto-fix arguments if needed
        fixed_args = fix_swap_arguments(
            plan.function_name,
            plan.function_args,
            abi
        )
        
        # Update plan with fixed args
        plan.function_args = fixed_args
        
        print("\n" + "="*60)
        print("PHASE 2: EXECUTION (PYTHON ONLY)")
        print("="*60)
        
        # Execute with fixed args
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
            return {"type": "error", "message": "Transaction data too short"}
        
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
        return {"type": "error", "message": f"Failed: {str(e)}"}