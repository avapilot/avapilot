"""
Chat Agent - Single orchestrator with all tools and memory
"""

import time
import json
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_vertexai import ChatVertexAI
from tools import get_token_address, get_contract_abi, read_contract_function
from transaction_tool import generate_blockchain_transaction


# Global memory checkpointer
MEMORY_SAVER = MemorySaver()


class AgentState(MessagesState):
    """Extend MessagesState to add iteration tracking"""
    iteration_count: int = 0


CHAT_PROMPT = """You are AvaPilot, a helpful blockchain assistant for Avalanche.

**Available Tools:**

1. **generate_blockchain_transaction** - For ACTIONS that change blockchain state
   - Swapping tokens
   - Transferring assets
   - Approving spending
   - Staking/unstaking
   Use when user wants to DO something

2. **read_contract_function** - For QUERIES about blockchain state
   - Check balances: read_contract_function(token_address, "balanceOf", [user_address])
   - Check allowances: read_contract_function(token_address, "allowance", [owner, spender])
   - Get token info: read_contract_function(token_address, "decimals", [])
   - Get token symbol: read_contract_function(token_address, "symbol", [])
   - Get contract owner: read_contract_function(contract_address, "owner", [])
   Use when user wants to KNOW something

3. **get_token_address** - Get contract address for tokens (WAVAX, USDC)

4. **get_contract_abi** - Get ABI to see available functions

**Decision Guide:**
- "Swap X for Y" → generate_blockchain_transaction
- "What's my balance?" → read_contract_function
- "Transfer X to Y" → generate_blockchain_transaction
- "Check allowance" → read_contract_function
- "What does contract X do?" → get_contract_abi, then explain
- "Who owns contract X?" → get_contract_abi, then read_contract_function("owner", [])
- "How does X work?" → answer directly with your knowledge

**For Contract Information Queries:**
1. Automatically fetch ABI with get_contract_abi
2. Analyze the ABI to understand the contract
3. If user asks about owner, check if owner() function exists
4. If it exists, call read_contract_function to get the owner address
5. DO NOT ask for permission - just do it!

**For Balance Queries:**
1. Call read_contract_function to get raw balance
2. Call read_contract_function to get decimals
3. Calculate: display_balance = raw_balance / (10 ** decimals)
4. Format nicely for user

**For Transaction Requests:**
- If user provides ALL details (amount, tokens, contract) → immediately call generate_blockchain_transaction
- If ANY detail is missing → ask the user
- Do NOT ask for confirmation if user already provided everything

**Example Flow for "What is the owner of 0xABC?":**
Step 1: Call get_contract_abi("0xABC")
Step 2: Parse ABI and look for owner() function
Step 3: If found, call read_contract_function("0xABC", "owner", [])
Step 4: Return: "The owner of this contract is 0xDEF..."

**IMPORTANT:** Be proactive! Don't ask permission to use tools - just use them to answer the user's question.

Be helpful, clear, and accurate!

Current timestamp: {timestamp}
"""


def create_chat_agent():
    """Creates the chat agent with memory"""
    
    tool_list = [
        generate_blockchain_transaction,
        read_contract_function,
        get_token_address,
        get_contract_abi
    ]
    
    model = ChatVertexAI(
        model="gemini-2.0-flash",
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
        
        messages = state['messages']
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "call_tools"
        return END
    
    def call_model(state):
        current_count = state.get('iteration_count', 0)
        print(f"[CHAT AGENT] Iteration {current_count + 1}")
        
        # DEBUG: Show loaded messages from checkpointer
        messages = state['messages']
        print(f"[MEMORY] Loaded {len(messages)} messages from checkpointer")
        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            if hasattr(msg, 'content'):
                content_preview = str(msg.content)[:80] if msg.content else "empty"
            else:
                content_preview = "no content"
            print(f"  [{i}] {msg_type}: {content_preview}...")
        
        # Add system prompt as first message if not present
        current_timestamp = int(time.time())
        system_content = CHAT_PROMPT.format(timestamp=current_timestamp)
        
        # Check if first message is system prompt
        if not messages or not (hasattr(messages[0], 'type') and messages[0].type == 'system'):
            print(f"[MEMORY] Adding system prompt to message history")
            messages = [SystemMessage(content=system_content)] + messages
        else:
            print(f"[MEMORY] System prompt already present")
        
        print(f"[MEMORY] Sending {len(messages)} messages to LLM")
        
        response = model.invoke(messages)
        
        print(f"[MEMORY] LLM response type: {type(response).__name__}")
        if hasattr(response, 'content'):
            print(f"[MEMORY] Response preview: {str(response.content)[:100]}...")
        
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
    
    # KEY: Compile with memory checkpointer
    return workflow.compile(checkpointer=MEMORY_SAVER)


def run_chat_agent(
    message: str, 
    user_address: str = None,
    conversation_id: str = None
) -> dict:
    """
    Runs the chat agent with memory
    
    Args:
        message: User's message
        user_address: User's wallet address
        conversation_id: Unique conversation ID (thread_id)
    
    Returns:
        {
            "type": "text" | "transaction" | "error",
            "message": str,
            "transaction": {...} (if type is transaction)
        }
    """
    print("\n" + "#"*60)
    print("CHAT AGENT STARTED")
    print(f"Conversation ID: {conversation_id}")
    print("#"*60)
    
    # Build full message with context
    full_message = message
    if user_address:
        full_message += f"\n\n**Context:** User's wallet is {user_address}"
    
    # Create input with just the new message
    # LangGraph will automatically load previous messages from checkpointer
    inputs = {
        "messages": [HumanMessage(content=full_message)],
        "iteration_count": 0
    }
    
    # KEY: Pass conversation_id as thread_id in config
    config = {"configurable": {"thread_id": conversation_id}}
    
    print(f"[MEMORY] Config: {config}")
    
    graph = create_chat_agent()
    
    # Accumulate ALL messages
    all_messages = []
    
    for output in graph.stream(inputs, config=config):
        for key, value in output.items():
            if 'messages' in value:
                all_messages.extend(value['messages'])
    
    print(f"[MEMORY] Total messages in response: {len(all_messages)}")
    
    print("#"*60)
    print("CHAT AGENT COMPLETE")
    print("#"*60 + "\n")
    
    if not all_messages:
        return {
            "type": "error",
            "message": "No response generated"
        }
    
    # Check if transaction was generated
    for i, msg in enumerate(all_messages):
        if isinstance(msg, ToolMessage) and msg.name == 'generate_blockchain_transaction':
            try:
                tx_result = json.loads(msg.content)
                
                if 'error' in tx_result:
                    ai_message = all_messages[-1].content if all_messages[-1].content else ""
                    return {
                        "type": "text",
                        "message": f"{ai_message}\n\nError: {tx_result['error']}"
                    }
                
                if 'to' in tx_result and 'data' in tx_result and 'value' in tx_result:
                    ai_message = all_messages[-1].content if all_messages[-1].content else ""
                    
                    return {
                        "type": "transaction",
                        "transaction": tx_result,
                        "message": ai_message or "Transaction ready to sign"
                    }
                    
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"[ERROR] {e}")
                continue
    
    # No transaction - just text response
    last_message = all_messages[-1]
    response_text = last_message.content if last_message.content else "I couldn't generate a response."
    
    return {
        "type": "text",
        "message": response_text
    }