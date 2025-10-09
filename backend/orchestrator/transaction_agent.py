"""
Transaction Agent - Specialized for generating blockchain transactions
This is a focused sub-agent that ONLY generates transactions
"""

import time
import json
import traceback
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage  # ← Changed from FunctionMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_google_vertexai import ChatVertexAI
import tools


# Agent State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    iteration_count: int


# Transaction-focused system prompt
TRANSACTION_PROMPT = """You are a blockchain transaction generator for Avalanche.

**Your ONLY job:** Generate a valid unsigned transaction.

**Process:**
1. Call get_contract_abi to get the contract ABI
2. **If the action mentions token SYMBOLS (like "AVAX", "USDC", "WAVAX"), call get_token_address for EACH symbol**
3. Identify the correct function from the ABI
4. Call generate_transaction with exact parameters

**CRITICAL RULES:**
- For swaps, you need token ADDRESSES not symbols
- AVAX swaps always use WAVAX address in the path
- Call get_token_address("WAVAX") for the wrapped AVAX address
- Call get_token_address("USDC") for USDC address
- ALWAYS call generate_transaction - never just describe
- Use integers for uint256 (not floats)
- For deadlines: {timestamp} + 1200
- User's wallet address is provided in context

**Example for "swap AVAX for USDC":**
1. Call get_token_address("WAVAX") → get WAVAX address
2. Call get_token_address("USDC") → get USDC address  
3. Use BOTH addresses in the path parameter: [WAVAX_address, USDC_address]

**Current timestamp:** {timestamp}
"""


def create_transaction_agent():
    """Creates the transaction agent graph"""
    
    # Only tools needed for transactions
    tool_list = [
        tools.get_token_address,
        tools.get_contract_abi,
        tools.generate_transaction
    ]
    
    model = ChatVertexAI(
        model="gemini-2.0-flash-exp",
        location="global",
        project="avapilot"
    ).bind_tools(tool_list)
    
    tool_node = ToolNode(tool_list)
    
    def tool_node_with_logging(state):
        print("[TX AGENT] Executing tools...")
        result = tool_node.invoke(state)
        print("[TX AGENT] Tools complete")
        return result
    
    def should_continue(state):
        iteration_count = state.get('iteration_count', 0)
        if iteration_count > 10:
            return END
        
        last_message = state['messages'][-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "call_tools"
        return END
    
    def call_model(state):
        current_count = state.get('iteration_count', 0)
        print(f"[TX AGENT] Iteration {current_count + 1}")
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
    Runs the transaction agent
    
    Returns:
        {
            "type": "transaction" | "error",
            "transaction": {...} or None,
            "message": str
        }
    """
    print("\n" + "="*60)
    print("TRANSACTION AGENT STARTED")
    print("="*60)
    
    current_timestamp = int(time.time())
    system_prompt = TRANSACTION_PROMPT.format(timestamp=current_timestamp)
    
    full_message = message
    if user_address:
        full_message += f"\n\nUser's wallet: {user_address}"
    if contract_address:
        full_message += f"\nContract: {contract_address}"
    
    inputs = {
        "messages": [
            HumanMessage(content=system_prompt),
            HumanMessage(content=full_message)
        ],
        "iteration_count": 0
    }
    
    graph = create_transaction_agent()
    
    # Accumulate ALL messages from ALL nodes
    all_messages = []
    
    for output in graph.stream(inputs):
        for key, value in output.items():
            # Collect messages from every node
            if 'messages' in value:
                all_messages.extend(value['messages'])
    
    print("="*60)
    print("TRANSACTION AGENT COMPLETE")
    print("="*60 + "\n")
    
    if not all_messages:
        return {
            "type": "error",
            "message": "Transaction agent failed to respond"
        }
    
    # Search through ALL accumulated messages with DETAILED logging
    print(f"[TX AGENT] Searching for transaction in messages...")
    print(f"[TX AGENT] Total messages: {len(all_messages)}")
    
    # First, show ALL message types for debugging
    print(f"[TX AGENT] Message types:")
    for i, msg in enumerate(all_messages):
        msg_type = type(msg).__name__
        print(f"  [{i}] {msg_type}", end="")
        if hasattr(msg, 'name'):
            print(f" - {msg.name}", end="")
        if hasattr(msg, 'content'):
            content_preview = str(msg.content)[:50] if msg.content else "empty"
            print(f" - content: {content_preview}...", end="")
        print()
    
    found_transaction = None
    
    for i, msg in enumerate(all_messages):
        if isinstance(msg, ToolMessage):  # ← Changed from FunctionMessage
            print(f"\n[TX AGENT] Examining message {i}: ToolMessage - {msg.name}")
            
            if msg.name == 'generate_transaction':
                print(f"[TX AGENT]   Content length: {len(msg.content)} chars")
                print(f"[TX AGENT]   Content preview: {msg.content[:200]}...")
                
                try:
                    tx_data = json.loads(msg.content)
                    print(f"[TX AGENT]   ✓ Parsed JSON successfully")
                    print(f"[TX AGENT]   Keys in parsed data: {list(tx_data.keys())}")
                    
                    # Check for error
                    if 'error' in tx_data:
                        print(f"[TX AGENT]   ✗ Has error: {tx_data['error']}")
                        continue
                    
                    # Check for valid transaction
                    has_to = 'to' in tx_data
                    has_data = 'data' in tx_data
                    has_value = 'value' in tx_data
                    
                    print(f"[TX AGENT]   Field check: to={has_to}, data={has_data}, value={has_value}")
                    
                    if has_to and has_data and has_value:
                        print(f"[TX AGENT]   ✓✓✓ Valid transaction found!")
                        found_transaction = tx_data
                        # Keep looking for the LAST successful one
                    else:
                        print(f"[TX AGENT]   ✗ Missing required fields")
                        
                except json.JSONDecodeError as e:
                    print(f"[TX AGENT]   ✗ JSON parse error: {e}")
                    continue
                except Exception as e:
                    print(f"[TX AGENT]   ✗ Error: {e}")
                    traceback.print_exc()
                    continue
    
    # If we found a transaction, return it
    if found_transaction:
        print(f"\n[TX AGENT] ✓✓✓ RETURNING TRANSACTION ✓✓✓")
        
        # Get AI's final message for context (if any)
        ai_message = ""
        if all_messages and hasattr(all_messages[-1], 'content'):
            ai_message = all_messages[-1].content or ""
        
        return {
            "type": "transaction",
            "transaction": found_transaction,
            "message": ai_message or "Transaction generated successfully"
        }
    
    # No valid transaction found
    print(f"\n[TX AGENT] ✗✗✗ NO VALID TRANSACTION FOUND ✗✗✗")
    return {
        "type": "error",
        "message": "Failed to generate transaction"
    }