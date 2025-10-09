from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import uuid
import json
import re
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, FunctionMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_google_vertexai import ChatVertexAI
import tools  

# --- Configuration ---
# Set your Google Cloud Project ID
PROJECT_ID = "avapilot" 
os.environ["GCLOUD_PROJECT"] = PROJECT_ID

# Initialize the Flask App
app = Flask(__name__)
CORS(app)

# --- Initialize Model and Bind Tools ---
# Create a list of the tools we want the agent to have
tool_list = [tools.get_token_address, tools.get_contract_abi, tools.generate_transaction]

# Initialize the LLM and bind the tools to it
model = ChatVertexAI(
    model="gemini-2.5-flash",  # Latest stable model
    location="global",  # Uses global endpoint
    project="avapilot"
).bind_tools(tool_list)

# --- Agent State Definition ---
# This defines the "memory" of our agent.
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

# --- Node Definitions ---
# The ToolNode will automatically call the correct tool for us
tool_node = ToolNode(tool_list)

def should_continue(state):
    # This function decides what to do next.
    last_message = state['messages'][-1]
    # If the LLM response contains a tool call, we execute the tool.
    if last_message.tool_calls:
        return "call_tools"
    # Otherwise, we end the conversation turn.
    return END

def call_model(state):
    # This is the main "thinking" step of the agent.
    print("---AGENT IS CALLING THE LLM---")
    response = model.invoke(state['messages'])
    # We return the LLM's response to add to the conversation history
    return {"messages": [response]}

# --- Graph Definition ---
# This defines the "thinking loop" of the agent.
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("call_tools", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "call_tools": "call_tools",
        END: END
    }
)
workflow.add_edge('call_tools', 'agent')
graph = workflow.compile()

# --- System Prompt ---
SYSTEM_PROMPT = """You are AvaPilot, an expert AI assistant for building transactions on the Avalanche blockchain.
Your goal is to help a user execute a transaction by generating a valid, unsigned transaction object.

You have access to these tools:
- `get_contract_abi(contract_address: str)`: Gets the ABI for a smart contract.
- `get_token_address(token_symbol: str)`: Gets the contract address for a token like WAVAX or USDC.
- `generate_transaction(...)`: Generates the final transaction object.

When a user asks to perform an action like a swap:
1. Your first step is ALWAYS to call `get_contract_abi` to understand the contract.
2. Figure out the correct function to use (e.g., `swapExactAVAXForTokens`).
3. For any token symbols (like "USDC"), use the `get_token_address` tool to find its address. The `path` for a swap is an array of addresses, e.g., [WAVAX_ADDRESS, USDC_ADDRESS].
4. **Assume default values for safety and convenience if not provided:**
   - For `amountOutMin` (slippage), always use `0`.
   - For `deadline`, calculate the current Unix timestamp and add 1200 seconds (20 minutes).
   - The `to` address for a swap is always the user's own wallet address.
5. Once you have ALL the necessary arguments, call the `generate_transaction` tool to build the final transaction. Do not ask the user for information you can find or assume.

Always return the transaction object in the response so the frontend can prompt the user's wallet.
"""

# --- API Endpoint ---
@app.route("/chat", methods=['POST'])
def chat():
    """
    This endpoint now uses the LangGraph agent to process the request.
    """
    req_json = request.get_json()
    message = req_json.get("message")

    # --- EXTRACT USER ADDRESS FROM CONTEXT ---
    context = req_json.get("context", {})
    user_address = context.get("user_address")

    # Add the user's address to the prompt if it exists
    full_message = message
    if user_address:
        full_message += f"\n\n(System context: The user's wallet address is {user_address})"
    # --- END OF ADDED LOGIC ---

    if not message:
        return jsonify({"error": "message field is required"}), 400

    # Create the input for the graph, using the new full_message
    inputs = {"messages": [
        HumanMessage(content=SYSTEM_PROMPT), 
        HumanMessage(content=full_message)  # Use the message that includes the address
    ]}

    # Stream the agent's response
    final_response = None
    for output in graph.stream(inputs):
        for key, value in output.items():
            if key == "agent":
                final_response = value

    # Extract the final AI message
    last_message = final_response['messages'][-1] if final_response else None
    
    if not last_message:
        return jsonify({
            "conversation_id": f"conv_{uuid.uuid4()}",
            "response_type": "error",
            "payload": {"message": "No response generated."}
        })

    response_text = last_message.content

    # Check if generate_transaction was called by looking at tool calls in the conversation
    has_transaction = False
    transaction_obj = None
    
    # Look through all messages for tool calls and responses
    for msg in final_response['messages']:
        # Check if this message has tool calls
        if hasattr(msg, 'tool_calls') and msg.tool_calls:
            for tool_call in msg.tool_calls:
                if tool_call.get('name') == 'generate_transaction':
                    has_transaction = True
        
        # Check if this is a function message (tool response)
        if isinstance(msg, FunctionMessage):
            try:
                # Try to parse the tool response as a transaction
                content = msg.content
                if isinstance(content, str) and '{' in content:
                    # Try to extract JSON from the response
                    json_match = re.search(r'\{[^}]+\}', content)
                    if json_match:
                        potential_tx = json.loads(json_match.group())
                        if 'to' in potential_tx and 'data' in potential_tx:
                            transaction_obj = potential_tx
            except:
                pass

    if has_transaction and transaction_obj:
        return jsonify({
            "conversation_id": f"conv_{uuid.uuid4()}",
            "response_type": "transaction",
            "payload": {
                "transaction": transaction_obj,
                "message": "Transaction ready to sign"
            }
        })
    else:
        # Regular text response
        return jsonify({
            "conversation_id": f"conv_{uuid.uuid4()}",
            "response_type": "text",
            "payload": {
                "message": response_text
            }
        })

# This part is for local testing
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)