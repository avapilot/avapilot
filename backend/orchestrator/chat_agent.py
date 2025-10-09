"""
Chat Agent - Master orchestrator that can answer questions AND generate transactions
"""

import time
import json
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage  # ← Changed from FunctionMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_google_vertexai import ChatVertexAI
import tools
from transaction_tool import generate_blockchain_transaction


# Agent State
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    iteration_count: int


# Master orchestrator prompt
CHAT_PROMPT = """You are AvaPilot, an AI assistant for Avalanche blockchain.

**Your Role:** Help users through conversation. You can both answer questions AND generate transactions.

**Available Tools:**
- get_contract_abi(contract_address): Fetch contract ABI
- get_token_address(symbol): Look up token addresses (WAVAX, USDC)
- generate_blockchain_transaction(action_description, contract_address, user_address): Generate a transaction

**How to Handle Requests:**

**For QUESTIONS (what, how, why, explain):**
- Use get_contract_abi if needed
- Provide clear, helpful answers
- Do NOT call generate_blockchain_transaction

**For ACTIONS (swap, transfer, send, approve, etc.):**
1. **Check if you have all required information:**
   - Amount to swap/transfer
   - Which tokens/contracts
   - Which contract address to use
   
2. **If ANY information is missing, ASK the user for it**

3. **If you have ALL information, IMMEDIATELY call generate_blockchain_transaction with:**
   - action_description: Full description (e.g., "swap 0.01 AVAX for USDC")
   - contract_address: The target contract
   - user_address: From context
   
   **Do NOT ask for confirmation - just generate the transaction!**

4. Present the result to the user

**CRITICAL:** If the user provides ALL details (amount, tokens, contract), you MUST call generate_blockchain_transaction immediately. Do NOT ask "is that correct?" - just do it!

**Current timestamp:** {timestamp}
"""


def create_chat_agent():
    """Creates the chat agent graph"""
    
    tool_list = [
        tools.get_token_address,
        tools.get_contract_abi,
        generate_blockchain_transaction
    ]
    
    model = ChatVertexAI(
        model="gemini-2.0-flash-exp",
        location="global",
        project="avapilot"
    ).bind_tools(tool_list)
    
    tool_node = ToolNode(tool_list)
    
    def tool_node_with_logging(state):
        print("[CHAT AGENT] Executing tools...")
        result = tool_node.invoke(state)
        print("[CHAT AGENT] Tools complete")
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
        print(f"[CHAT AGENT] Iteration {current_count + 1}")
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


def run_chat_agent(message: str, user_address: str = None) -> dict:
    """
    Runs the chat agent (master orchestrator)
    
    Returns:
        {
            "type": "text" | "transaction" | "error",
            "message": str,
            "transaction": {...} (if type is transaction)
        }
    """
    print("\n" + "#"*60)
    print("CHAT AGENT STARTED")
    print("#"*60)
    
    current_timestamp = int(time.time())
    system_prompt = CHAT_PROMPT.format(timestamp=current_timestamp)
    
    full_message = message
    if user_address:
        full_message += f"\n\n**Context:** User's wallet is {user_address}"
    
    inputs = {
        "messages": [
            HumanMessage(content=system_prompt),
            HumanMessage(content=full_message)
        ],
        "iteration_count": 0
    }
    
    graph = create_chat_agent()
    
    # Accumulate ALL messages
    all_messages = []
    
    for output in graph.stream(inputs):
        for key, value in output.items():
            if 'messages' in value:
                all_messages.extend(value['messages'])
    
    print("#"*60)
    print("CHAT AGENT COMPLETE")
    print("#"*60 + "\n")
    
    if not all_messages:
        return {
            "type": "error",
            "message": "No response generated"
        }
    
    # Check if transaction was generated via the tool
    print("[CHAT AGENT] Searching for transaction in messages...")
    print(f"[CHAT AGENT] Total messages: {len(all_messages)}")
    
    for i, msg in enumerate(all_messages):
        if isinstance(msg, ToolMessage) and msg.name == 'generate_blockchain_transaction':
            try:
                print(f"[CHAT AGENT] Found generate_blockchain_transaction in message {i}")
                print(f"[CHAT AGENT] Content preview: {msg.content[:100]}...")
                
                tx_result = json.loads(msg.content)
                
                print(f"[CHAT AGENT] Parsed JSON successfully")
                print(f"[CHAT AGENT] Keys: {list(tx_result.keys())}")
                
                # Check if it's an error
                if 'error' in tx_result:
                    print(f"[CHAT AGENT] Transaction tool returned error")
                    ai_message = all_messages[-1].content if all_messages[-1].content else ""
                    return {
                        "type": "text",
                        "message": f"{ai_message}\n\nError: {tx_result['error']}"
                    }
                
                # Check if it's a valid transaction (has to, data, value)
                if 'to' in tx_result and 'data' in tx_result and 'value' in tx_result:
                    print(f"[CHAT AGENT] ✓✓✓ Valid transaction found!")
                    
                    # Get AI's explanation message
                    ai_message = all_messages[-1].content if all_messages[-1].content else ""
                    
                    return {
                        "type": "transaction",
                        "transaction": tx_result,
                        "message": ai_message or "Transaction ready to sign"
                    }
                else:
                    print(f"[CHAT AGENT] Transaction missing required fields")
                    
            except json.JSONDecodeError as e:
                print(f"[CHAT AGENT] JSON parse error: {e}")
                continue
            except Exception as e:
                print(f"[CHAT AGENT] Error: {e}")
                continue
    
    # No transaction - just text response
    print("[CHAT AGENT] No transaction found, returning text response")
    last_message = all_messages[-1]
    response_text = last_message.content if last_message.content else "I couldn't generate a response."
    
    return {
        "type": "text",
        "message": response_text
    }