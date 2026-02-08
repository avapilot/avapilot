"""
Chat Agent - Single orchestrator with all tools and memory
"""

import time
import json
from langchain_core.messages import BaseMessage, ToolMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from tools import (
    get_token_address,
    get_contract_abi,
    read_contract_function,
    analyze_contract,
    explore_contract_state,
    get_item_by_id,
    convert_wei_to_avax,
    get_insurance_details,
)
from transaction_tool import generate_blockchain_transaction
from agent_config import config

# In-memory checkpointer — conversations reset on server restart
MEMORY_SAVER = MemorySaver()


class AgentState(MessagesState):
    """Extend MessagesState to add iteration tracking"""
    iteration_count: int = 0


CONTRACT_SCOPING_RULES = """
**CRITICAL SECURITY RULE - CONTRACT SCOPING:**

You are currently scoped to ONLY work with this contract:
**Allowed Contract:** `{allowed_contract}`

**YOU MUST:**
1. ONLY generate transactions for the allowed contract address above
2. ONLY provide information about the allowed contract when asked about contracts
3. If user asks about a different contract, politely explain you're scoped
4. Never suggest or recommend other contract addresses

**NEVER generate transactions to any contract except {allowed_contract}.**
"""

CHAT_PROMPT = """You are AvaPilot, a helpful blockchain assistant for Avalanche.

{contract_scoping_rules}

**CRITICAL RULE: NEVER SAY "I CANNOT" WITHOUT TRYING FIRST!**

When user asks about contract data you don't know about:
1. **FIRST**: Call explore_contract_state() to discover available functions
2. **THEN**: Try reading discovered functions
3. **ONLY THEN**: Say you cannot help (if truly impossible)

**Available Tools:**

1. **generate_blockchain_transaction** - For ACTIONS that change blockchain state
   Use when user wants to DO something (swap, transfer, approve, stake)

2. **read_contract_function** - For QUERIES about blockchain state
   - Check balances, allowances, token info, contract state
   - Handles ALL return types including arrays, tuples, nested data
   Use when user wants to KNOW something

3. **convert_wei_to_avax** - MANDATORY for all balance/amount queries
   ANY time you see a number larger than 1,000 from a contract call, convert it first.
   1 AVAX = 1,000,000,000,000,000,000 Wei (18 decimals)

4. **get_token_address** - Get contract address for tokens (WAVAX, USDC)

5. **get_contract_abi** - Get raw ABI (rarely needed)

6. **analyze_contract** - DEEP contract analysis with dedicated agent
   After calling, extract and simplify the relevant parts for the user.
   Don't dump the entire report — answer the user's specific question.

7. **explore_contract_state** - USE THIS WHEN YOU DON'T KNOW WHAT FUNCTIONS EXIST
   Discovers zero-param view functions and single-param getters with sample IDs.

8. **get_item_by_id** - Smart ID lookup for when you know the item type

9. **get_insurance_details** - Specialized tool for insurance contracts

**Decision Guide:**
- "Show me available X" → explore_contract_state FIRST!
- "What does contract X do?" → analyze_contract
- "Swap X for Y" → generate_blockchain_transaction
- "What's my balance?" → read_contract_function + convert_wei_to_avax

**For Transaction Requests:**
- If user provides ALL details → immediately call generate_blockchain_transaction
- If ANY detail is missing → ask the user

Be proactive! Don't ask permission to use tools — just use them.
Be helpful, clear, and accurate!

Current timestamp: {timestamp}
"""


def create_chat_agent():
    """Creates the chat agent with in-memory checkpointing."""

    tool_list = [
        generate_blockchain_transaction,
        read_contract_function,
        get_token_address,
        get_contract_abi,
        analyze_contract,
        explore_contract_state,
        get_item_by_id,
        convert_wei_to_avax,
        get_insurance_details,
    ]

    model = config.create_model("chat_agent", tools=tool_list)
    tool_node = ToolNode(tool_list)

    def tool_node_with_logging(state):
        print("[CHAT AGENT] Executing tools...")
        result = tool_node.invoke(state)
        print("[CHAT AGENT] Tools complete")
        return result

    def should_continue(state):
        iteration_limit = config.get_iteration_limit("chat_agent")
        iteration_count = state.get("iteration_count", 0)

        if iteration_count > iteration_limit:
            print(f"Hit iteration limit ({iteration_count}/{iteration_limit}). Stopping.")
            return END

        last_message = state["messages"][-1]
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "call_tools"
        return END

    def call_model(state):
        current_count = state.get("iteration_count", 0)
        print(f"[CHAT AGENT] Iteration {current_count + 1}")

        messages = list(state["messages"])
        print(f"[MEMORY] Loaded {len(messages)} messages")

        if len(messages) > config.MESSAGE_TRIM_LIMIT:
            print(f"[MEMORY] Trimming: {len(messages)} -> {config.MESSAGE_TRIM_LIMIT}")
            messages = messages[-config.MESSAGE_TRIM_LIMIT:]

        if not messages:
            messages = [HumanMessage(content="Continue from previous context")]

        # Build system prompt
        allowed_contract = state.get("configurable", {}).get("allowed_contract")
        user_address = state.get("configurable", {}).get("user_address")
        scoping_rules = (
            CONTRACT_SCOPING_RULES.format(allowed_contract=allowed_contract)
            if allowed_contract
            else ""
        )

        system_content = CHAT_PROMPT.format(
            contract_scoping_rules=scoping_rules,
            timestamp=int(time.time()),
        ) + f"""

**CURRENT CONTEXT:**
- User's wallet address: `{user_address}`
- Allowed contract: `{allowed_contract}`
- Network: Avalanche Fuji Testnet

**IMPORTANT:** When calling `generate_blockchain_transaction`, pass:
  contract_address="{allowed_contract}", user_address="{user_address}"
"""

        has_system = any(
            hasattr(msg, "type") and msg.type == "system" for msg in messages
        )
        if not has_system:
            messages.insert(0, SystemMessage(content=system_content))

        if len(messages) < 2:
            messages.append(HumanMessage(content="Continue assisting the user"))

        response = model.invoke(messages)
        return {"messages": [response], "iteration_count": current_count + 1}

    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("call_tools", tool_node_with_logging)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent", should_continue, {"call_tools": "call_tools", END: END}
    )
    workflow.add_edge("call_tools", "agent")

    return workflow.compile(checkpointer=MEMORY_SAVER)


def run_chat_agent(
    message: str,
    user_address: str = None,
    conversation_id: str = None,
    allowed_contract: str = None,
) -> dict:
    """
    Runs the chat agent with in-memory persistence.

    Returns:
        {"type": "text"|"transaction"|"error", "message": str, "transaction": {...}}
    """
    print(f"\n{'#' * 60}")
    print("CHAT AGENT STARTED")
    print(f"Conversation ID: {conversation_id}")
    if allowed_contract:
        print(f"Scoped to: {allowed_contract}")
    print("#" * 60)

    full_message = message
    if user_address:
        full_message += f"\n\n**Context:** User's wallet is {user_address}"
    if allowed_contract:
        full_message += f"\n**Allowed Contract:** {allowed_contract}"

    inputs = {"messages": [HumanMessage(content=full_message)], "iteration_count": 0}

    config_dict = {
        "configurable": {
            "thread_id": conversation_id,
            "allowed_contract": allowed_contract,
        },
        "recursion_limit": config.get_recursion_limit("chat_agent"),
    }

    print(f"[MEMORY] thread_id: {conversation_id}")

    graph = create_chat_agent()
    all_messages = []

    for output in graph.stream(inputs, config=config_dict):
        for key, value in output.items():
            if "messages" in value:
                all_messages.extend(value["messages"])

    print(f"[MEMORY] Total messages in response: {len(all_messages)}")
    print(f"{'#' * 60}\nCHAT AGENT COMPLETE\n{'#' * 60}\n")

    if not all_messages:
        return {"type": "error", "message": "No response generated"}

    # Check for transaction in tool results
    for msg in all_messages:
        if isinstance(msg, ToolMessage) and msg.name == "generate_blockchain_transaction":
            try:
                tx_result = json.loads(msg.content)
                if "error" in tx_result:
                    ai_msg = all_messages[-1].content if all_messages[-1].content else ""
                    return {"type": "text", "message": f"{ai_msg}\n\nError: {tx_result['error']}"}

                if all(k in tx_result for k in ("to", "data", "value")):
                    ai_msg = all_messages[-1].content if all_messages[-1].content else ""
                    return {
                        "type": "transaction",
                        "transaction": tx_result,
                        "message": ai_msg or "Transaction ready to sign",
                    }
            except (json.JSONDecodeError, Exception):
                continue

    last_message = all_messages[-1]
    return {
        "type": "text",
        "message": last_message.content if last_message.content else "I couldn't generate a response.",
    }
