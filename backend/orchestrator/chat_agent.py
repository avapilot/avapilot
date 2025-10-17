"""
Chat Agent - Single orchestrator with all tools and memory
"""

import time
import json
import os
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage, trim_messages
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.prebuilt import ToolNode
from langchain_google_vertexai import ChatVertexAI
from tools import get_token_address, get_contract_abi, read_contract_function, analyze_contract
from transaction_tool import generate_blockchain_transaction

# Initialize Firestore checkpointer
from langgraph_checkpoint_firestore import FirestoreSaver


# Initialize Firestore with project_id only
project_id = os.getenv("GCP_PROJECT", "avapilot")

# FirestoreSaver creates its own client - just pass project_id
MEMORY_SAVER = FirestoreSaver(project_id=project_id)


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
   - **Get all contracts: read_contract_function(contract_address, "getAllContracts", [])**
   - **Get array data: This tool fully supports arrays (uint256[], address[], etc.)**
   
   **IMPORTANT: This tool handles ALL return types including:**
   - Arrays of any type (uint256[], address[], string[], etc.)
   - Tuples and structs
   - Nested data structures
   - Multiple return values
   
   Use when user wants to KNOW something. Don't refuse based on return type complexity

3. **get_token_address** - Get contract address for tokens (WAVAX, USDC)

4. **get_contract_abi** - Get raw ABI (rarely needed)

5. **analyze_contract** - DEEP contract analysis with dedicated agent
   - Returns comprehensive technical analysis report
   - **IMPORTANT: You MUST extract and simplify the relevant parts for the user**
   
   **After calling analyze_contract:**
   
   The tool returns a detailed technical report. Your job is to:
   1. Read the FULL analysis (including code snippets if available)
   2. Extract ONLY what answers the user's specific question
   3. Present in clear, conversational language
   4. Include specific details from source code if available
   5. Highlight risks with emoji (🚨 ⚠️ ✅)
   
   **Response Strategy by Question Type:**
   
   **"What does contract X do?"**
   → Extract: Purpose, main functions, what users can do
   → Format: 2-3 sentence summary + bullet points
   → Skip: Detailed code, security deep-dive
   
   **"How does function Y work?"** ⭐ THIS IS KEY
   → Extract: That specific function's actual code logic (if source available)
   → Show: Step-by-step what the function does internally
   → Include: Any checks, state changes, risks in that function
   → Format: Clear steps with explanations
   → Skip: Other functions, general contract info
   
   **"Can I lose money?"**
   → Extract: Financial risks, money flows, worst-case scenarios
   → Format: Direct yes/no + explanation + risk ratings
   → Skip: Technical implementation details
   
   **"Is contract X safe?"**
   → Extract: Security assessment, critical vulnerabilities
   → Format: Risk summary + specific issues + recommendations
   → Skip: Non-security functionality
   
   **CRITICAL for function-specific questions:**
   - If analysis includes source code details → INCLUDE THEM in your response
   - If analysis shows what lines of code do → EXPLAIN THEM simply
   - If analysis identifies function-specific risks → HIGHLIGHT THEM
   - Don't just say "based on ABI" if source code was analyzed
   
   **Example of extracting code details:**
   
   User: "How does triggerPayout work?"
   
   Analysis report includes:
   ```
   Line 249: require(!contracts[contractId].triggered, "Already triggered");
   Line 250: require(currentPrice <= triggerPrice, "Condition not met");
   Line 252: contracts[contractId].triggered = true;
   ```
   
   YOUR RESPONSE should be:
   "The triggerPayout function does 3 things:
   
   1. **Checks if not already triggered** - Prevents double payouts by verifying the contract hasn't been triggered yet
   
   2. **Verifies price condition** - Compares current price against the trigger price. If current price isn't low enough, the transaction fails
   
   3. **Marks as triggered** - Sets a flag so users can claim their payout via claimPayout()
   
   🚨 **Risk**: Anyone can call this with ANY price value - there's no oracle verification, so someone could input a false price to trigger payouts incorrectly."
   
   **Response Rules:**
   - Be conversational and helpful
   - Extract what matters to the user
   - If source code was analyzed, show actual logic (simplified)
   - Don't dump the entire technical report
   - Don't say "based on the analysis" - just answer directly
   - Keep it under 300 words unless user asks for detail

**Decision Guide:**
- "What does contract X do?" → analyze_contract
- "How does function Y work?" → analyze_contract + extract code logic
- "Can I lose money?" → analyze_contract + extract risks
- "Is X safe?" → analyze_contract + extract security assessment
- "Swap X for Y" → generate_blockchain_transaction
- "What's my balance?" → read_contract_function

**For Contract Information Queries:**
1. Call analyze_contract to get comprehensive analysis
2. Extract and simplify the relevant parts for the user
3. If user wants specific values (owner, balance), use read_contract_function
4. DO NOT ask for permission - just do it!

**For Balance Queries:**
1. Call read_contract_function to get raw balance
2. Call read_contract_function to get decimals
3. Calculate: display_balance = raw_balance / (10 ** decimals)
4. Format nicely for user

**For Transaction Requests:**
- If user provides ALL details (amount, tokens, contract) → immediately call generate_blockchain_transaction
- If ANY detail is missing → ask the user
- Do NOT ask for confirmation if user already provided everything

**IMPORTANT:** Be proactive! Don't ask permission to use tools - just use them to answer the user's question.

Be helpful, clear, and accurate!

Current timestamp: {timestamp}
"""


def create_chat_agent():
    """Creates the chat agent with Firestore memory"""
    
    tool_list = [
        generate_blockchain_transaction,
        read_contract_function,
        get_token_address,
        get_contract_abi,
        analyze_contract  # Add new tool
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
        
        # Get messages from state
        messages = list(state['messages'])
        print(f"[MEMORY] Loaded {len(messages)} messages from Firestore")
        
        # TRIM TO LAST 20 MESSAGES
        if len(messages) > 20:
            print(f"[MEMORY] Trimming {len(messages)} → 20 messages")
            messages = trim_messages(
                messages,
                max_tokens=20,
                strategy="last",
                token_counter=len,
                include_system=True,
                start_on="human"
            )
            print(f"[MEMORY] After trim: {len(messages)} messages")
        
        # Add system prompt if not present
        current_timestamp = int(time.time())
        system_content = CHAT_PROMPT.format(timestamp=current_timestamp)
        
        has_system = any(
            hasattr(msg, 'type') and msg.type == 'system' 
            for msg in messages
        )
        
        if not has_system:
            print(f"[MEMORY] Adding system prompt")
            messages.insert(0, SystemMessage(content=system_content))
        
        print(f"[MEMORY] Sending {len(messages)} messages to LLM")
        
        response = model.invoke(messages)
        
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
    
    # Use Firestore checkpointer
    return workflow.compile(checkpointer=MEMORY_SAVER)


def run_chat_agent(
    message: str, 
    user_address: str = None,
    conversation_id: str = None
) -> dict:
    """
    Runs the chat agent with Firestore memory
    
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
    # LangGraph will automatically load previous messages from Firestore
    inputs = {
        "messages": [HumanMessage(content=full_message)],
        "iteration_count": 0
    }
    
    # Pass conversation_id as thread_id in config
    config = {"configurable": {"thread_id": conversation_id}}
    
    print(f"[MEMORY] Using Firestore with thread_id: {conversation_id}")
    
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