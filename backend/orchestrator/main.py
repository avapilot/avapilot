"""
Main Flask Application - Single unified endpoint with memory
"""

import os
import uuid
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from chat_agent import run_chat_agent

# --- Configuration ---
PROJECT_ID = "avapilot" 
os.environ["GCLOUD_PROJECT"] = PROJECT_ID

# Initialize Flask App
app = Flask(__name__)
CORS(app)

# NEW: Widget file serving
WIDGET_DIR = os.path.join(os.path.dirname(__file__), '../../frontend/widget')

@app.route('/widget.js')
def serve_widget_js():
    """Serve the widget loader script"""
    try:
        return send_from_directory(WIDGET_DIR, 'widget.js', mimetype='application/javascript')
    except FileNotFoundError:
        return jsonify({"error": "widget.js not found"}), 404

@app.route('/widget-chat.html')
def serve_widget_chat():
    """Serve the widget chat interface"""
    try:
        return send_from_directory(WIDGET_DIR, 'widget-chat.html')
    except FileNotFoundError:
        return jsonify({"error": "widget-chat.html not found"}), 404

@app.route('/widget/config.js')
def serve_widget_config():
    """Serve widget configuration (optional)"""
    try:
        return send_from_directory(WIDGET_DIR, 'config.js', mimetype='application/javascript')
    except FileNotFoundError:
        return jsonify({"error": "config.js not found"}), 404

@app.route("/chat", methods=['POST'])
def chat():
    """
    Unified endpoint with memory + contract scoping support
    """
    req_json = request.get_json()
    message = req_json.get("message")
    context = req_json.get("context", {})
    user_address = context.get("user_address")
    
    # NEW: Get contract scoping info
    allowed_contract = context.get("allowed_contract")  # From widget
    api_key = context.get("api_key")  # For tracking
    
    conversation_id = req_json.get("conversation_id")
    if not conversation_id:
        conversation_id = f"conv_{uuid.uuid4()}"

    if not message:
        return jsonify({"error": "message field is required"}), 400

    print(f"\n{'#'*60}")
    print(f"# REQUEST: {message}")
    print(f"# Conversation: {conversation_id}")
    if allowed_contract:
        print(f"# Scoped to: {allowed_contract}")
    if api_key:
        print(f"# API Key: ***{api_key[-4:]}")
    print(f"{'#'*60}")
    
    # Run chat agent with contract restriction
    result = run_chat_agent(
        message=message,
        user_address=user_address,
        conversation_id=conversation_id,
        allowed_contract=allowed_contract  # NEW
    )
    
    # CRITICAL: Validate transaction target (defense in depth)
    if result["type"] == "transaction":
        tx_target = result["transaction"]["to"].lower()
        
        if allowed_contract and tx_target != allowed_contract.lower():
            print(f"[SECURITY] 🚨 Transaction blocked: {tx_target} != {allowed_contract}")
            return jsonify({
                "conversation_id": conversation_id,
                "response_type": "error",
                "payload": {
                    "message": f"🚨 Security violation: Transaction targets {tx_target} but widget is scoped to {allowed_contract}"
                }
            }), 403  # Forbidden
    
    print(f"{'#'*60}")
    print(f"# COMPLETE - Type: {result['type']}")
    print(f"{'#'*60}\n")
    
    # Build response
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


@app.route("/health", methods=['GET'])
def health():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "avapilot-orchestrator",
        "memory": "firestore",
        "message_limit": 20
    })


# This part is for local testing
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)