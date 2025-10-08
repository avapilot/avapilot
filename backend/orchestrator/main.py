from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import uuid
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
tool_list = [tools.get_dapp_schema]

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
# REPLACE the old placeholder 'call_tools' node with the new ToolNode
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
SYSTEM_PROMPT = """You are AvaPilot, an expert AI assistant for interacting with decentralized applications (dApps) on the Avalanche blockchain. 
Your primary goal is to help users understand and perform actions on dApps safely and easily.

You have access to a set of tools to gather information.

When a user asks a question (e.g., "what is this app?", "how do I swap?"), use your tools to get information and then explain it to the user in a clear, concise, and helpful way.

When a user asks you to perform an action (e.g., "swap 1 AVAX for USDC"), your job is to:
1.  First, understand the dApp by using the `get_dapp_schema` tool.
2.  Then, once you have the schema, your next step will be to prepare the transaction. (We will implement this part later).

Always think step-by-step.
"""

# --- API Endpoint ---
@app.route("/chat", methods=['POST'])
def chat():
    """
    This endpoint now uses the LangGraph agent to process the request.
    """
    req_json = request.get_json()
    message = req_json.get("message")

    if not message:
        return jsonify({"error": "message field is required"}), 400

    # Create the input for the graph
    inputs = {"messages": [
        HumanMessage(content=SYSTEM_PROMPT), 
        HumanMessage(content=message)
    ]}

    # Stream the agent's response
    # In a real app, you would stream this back to the user.
    # For now, we'll just collect the final response.
    final_response = None
    for output in graph.stream(inputs):
        # The final response is the last one from the "agent" node
        for key, value in output.items():
            if key == "agent":
                final_response = value

    # Extract the text content from the final AI message
    response_text = final_response['messages'][-1].content if final_response else "No response generated."

    # For now, we return a simple text response.
    # In a later step, this will return a TransactionObject if needed.
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