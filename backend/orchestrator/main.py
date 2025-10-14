"""
Main Flask Application - Single unified endpoint with memory
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import uuid
from chat_agent import run_chat_agent

# --- Configuration ---
# Set your Google Cloud Project ID
PROJECT_ID = "avapilot" 
os.environ["GCLOUD_PROJECT"] = PROJECT_ID

# Initialize the Flask App
app = Flask(__name__)
CORS(app)


@app.route("/chat", methods=['POST'])
def chat():
    """
    Unified endpoint with memory support
    """
    req_json = request.get_json()
    message = req_json.get("message")
    context = req_json.get("context", {})
    user_address = context.get("user_address")
    
    # KEY: Get or create conversation_id
    conversation_id = req_json.get("conversation_id")
    if not conversation_id:
        conversation_id = f"conv_{uuid.uuid4()}"

    if not message:
        return jsonify({"error": "message field is required"}), 400

    print(f"\n{'#'*60}")
    print(f"# REQUEST: {message}")
    print(f"# Conversation: {conversation_id}")
    print(f"{'#'*60}")
    
    # Run chat agent with conversation_id
    result = run_chat_agent(
        message=message,
        user_address=user_address,
        conversation_id=conversation_id
    )
    
    print(f"{'#'*60}")
    print(f"# COMPLETE - Type: {result['type']}")
    print(f"{'#'*60}\n")
    
    # Build response with conversation_id
    if result["type"] == "transaction":
        return jsonify({
            "conversation_id": conversation_id,
            "response_type": "transaction",
            "payload": {
                "transaction": result["transaction"],
                "message": result["message"]
            }
        })
    elif result["type"] == "error":
        return jsonify({
            "conversation_id": conversation_id,
            "response_type": "error",
            "payload": {"message": result["message"]}
        }), 400
    else:  # text
        return jsonify({
            "conversation_id": conversation_id,
            "response_type": "text",
            "payload": {"message": result["message"]}
        })


# This part is for local testing
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)