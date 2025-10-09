"""
Main Flask Application - Single unified endpoint
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import uuid
from chat_agent import run_chat_agent

app = Flask(__name__)
CORS(app)


@app.route("/chat", methods=['POST'])
def chat():
    """
    Unified endpoint - chat agent orchestrates everything
    """
    req_json = request.get_json()
    message = req_json.get("message")
    context = req_json.get("context", {})
    user_address = context.get("user_address")

    if not message:
        return jsonify({"error": "message field is required"}), 400

    print(f"\n{'#'*60}")
    print(f"# REQUEST: {message}")
    print(f"{'#'*60}")
    
    # Run chat agent - it handles everything
    result = run_chat_agent(message, user_address)
    
    print(f"{'#'*60}")
    print(f"# COMPLETE - Type: {result['type']}")
    print(f"{'#'*60}\n")
    
    # Build response
    if result["type"] == "transaction":
        return jsonify({
            "conversation_id": f"conv_{uuid.uuid4()}",
            "response_type": "transaction",
            "payload": {
                "transaction": result["transaction"],
                "message": result["message"]
            }
        })
    elif result["type"] == "error":
        return jsonify({
            "conversation_id": f"conv_{uuid.uuid4()}",
            "response_type": "error",
            "payload": {"message": result["message"]}
        }), 400
    else:  # text
        return jsonify({
            "conversation_id": f"conv_{uuid.uuid4()}",
            "response_type": "text",
            "payload": {"message": result["message"]}
        })


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)