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
import os


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    iteration_count: int


# Even more aggressive prompting
PLANNING_PROMPT = """You are a transaction planning agent for Avalanche blockchain.

**YOUR ONLY JOB:** Plan the transaction parameters for a specific contract function call.

**Available Tools (for planning only - NOT contract functions):**
- get_token_address: Get token contract addresses (WAVAX, USDC, etc.)
- get_contract_abi: Get the contract's ABI to validate function names

**DO NOT confuse these tools with contract functions!**

**Example 1: Token Swap**
User action: "Swap 1 AVAX for USDC on TraderJoe"

Your plan:
```json
{
  "function_name": "swapExactAVAXForTokens",
  "args": [0, ["0x1D308089a2D1Ced3f1Ce36B1FcaF815b07217be3", "0x5425890298aed601595a70AB815c96711a31Bc65"], "0xe2c3465d71d5a2ea1efc52ccadd843bcc93ca18d", 1699999999],
  "args_types": ["uint256", "address[]", "address", "uint256"],
  "value_in_avax": 1.0,
  "estimated_gas": 250000
}
```

**Example 2: Purchase Insurance** ← ADD THIS
User action: "purchase insurance contract with ID 26 for 0.01 AVAX"

Step 1: Check if you need the ABI (only if you don't know the function name)
- If action says "purchaseInsurance(26)" → You already know the function name
- If action just says "buy insurance 26" → Use get_contract_abi tool first

Step 2: Plan the transaction
```json
{
  "function_name": "purchaseInsurance",
  "args": [26],
  "args_types": ["uint256"],
  "value_in_avax": 0.01,
  "estimated_gas": 150000
}
```

**CRITICAL RULES:**
1. ✅ Use get_token_address if you need token addresses
2. ✅ Use get_contract_abi if you need to discover function names
3. ❌ NEVER put get_contract_abi or get_token_address in function_name
4. ❌ function_name must ONLY be actual contract functions like:
   - swapExactAVAXForTokens
   - purchaseInsurance
   - approve
   - transfer
   - claimPayout
5. If action description already mentions the function name (e.g., "purchaseInsurance(26)"), use it directly without calling get_contract_abi

**When to use get_contract_abi:**
- ✅ User says "buy insurance" but you don't know if it's purchaseInsurance or buyInsurance
- ✅ User mentions a function you haven't seen before
- ❌ User already says "call purchaseInsurance(26)"
- ❌ You already know the function name from context

**Your Response Format:**
Return a TransactionPlan with:
- function_name: The CONTRACT function to call (not get_contract_abi!)
- args: The function arguments
- args_types: Solidity types
- value_in_avax: AVAX to send with transaction
- estimated_gas: Gas estimate

Contract address: {contract_address}
User address: {user_address}
User's action: {action_description}

Plan the transaction now:
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
    """Creates agent for planning only with model selection"""
    
    tool_list = [get_token_address, get_contract_abi]
    
    # ========================================
    # MODEL CONFIGURATION (same as chat_agent)
    # ========================================
    model_choice = os.getenv("LLM_MODEL", "openai")  # Default: openai
    project_id = os.getenv("GCP_PROJECT", "avapilot")
    
    # ✅ OPTION 1: OpenAI GPT
    if model_choice == "openai":
        from google.auth import default
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        from langchain_openai import ChatOpenAI
        
        # Hybrid credentials
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            print(f"[TRANSACTION] Using service account from {credentials_path}")
        else:
            credentials, _ = default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            print(f"[TRANSACTION] Using default credentials (Cloud Run)")
        
        credentials.refresh(Request())
        
        region = "global"
        base_url = f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/endpoints/openapi"
        
        model = ChatOpenAI(
            base_url=base_url,
            api_key=credentials.token,
            model="openai/gpt-oss-120b-maas",
            temperature=0.3,
        ).bind_tools(tool_list).with_structured_output(TransactionPlan)
        
        print(f"[TRANSACTION] Using OpenAI GPT-OSS-120B (region: {region})")
    
    # ✅ OPTION 2: Qwen 3
    elif model_choice == "qwen":
        from google.auth import default
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        from langchain_openai import ChatOpenAI
        
        # Hybrid credentials
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if credentials_path and os.path.exists(credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/cloud-platform']
            )
            print(f"[TRANSACTION] Using service account from {credentials_path}")
        else:
            credentials, _ = default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            print(f"[TRANSACTION] Using default credentials (Cloud Run)")
        
        credentials.refresh(Request())
        
        region = "us-south1"
        base_url = f"https://us-south1-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{region}/endpoints/openapi"
        
        model = ChatOpenAI(
            base_url=base_url,
            api_key=credentials.token,
            model="qwen/qwen3-235b-a22b-instruct-2507-maas",
            temperature=0.3,
        ).bind_tools(tool_list).with_structured_output(TransactionPlan)
        
        print(f"[TRANSACTION] Using Qwen 3 235B (region: {region})")
    
    # ✅ OPTION 3: Gemini (Default - Recommended)
    else:  # gemini
        model = ChatVertexAI(
            model="gemini-2.5-flash",
            location="global",
            project=project_id,
            temperature=0.3,
        ).bind_tools(tool_list).with_structured_output(TransactionPlan)
        
        print(f"[TRANSACTION] Using Gemini 2.0 Flash (recommended)")
    
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