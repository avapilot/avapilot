"""
Main Flask Application - Single unified endpoint with memory
"""

import os
import uuid
import re
import time
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from chat_agent import run_chat_agent
from error_tracker import log_error, log_warning, log_metric, ErrorType
from rate_limiter import rate_limit
from agent_config import config

app = Flask(__name__)
CORS(app)

WIDGET_DIR = os.path.join(os.path.dirname(__file__), "../../frontend/widget")


@app.route("/widget.js")
def serve_widget_js():
    try:
        return send_from_directory(WIDGET_DIR, "widget.js", mimetype="application/javascript")
    except FileNotFoundError:
        return jsonify({"error": "widget.js not found"}), 404


@app.route("/widget-chat.html")
def serve_widget_chat():
    try:
        return send_from_directory(WIDGET_DIR, "widget-chat.html")
    except FileNotFoundError:
        return jsonify({"error": "widget-chat.html not found"}), 404


@app.route("/widget/config.js")
def serve_widget_config():
    try:
        return send_from_directory(WIDGET_DIR, "config.js", mimetype="application/javascript")
    except FileNotFoundError:
        return jsonify({"error": "config.js not found"}), 404


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "service": "avapilot-orchestrator",
        "provider": config.LLM_PROVIDER,
        "memory": "in-memory",
        "validation": "enabled",
    })


@app.route("/metrics", methods=["GET"])
def metrics():
    return jsonify({
        "status": "healthy",
        "timestamp": int(time.time()),
        "metrics": {
            "provider": config.LLM_PROVIDER,
            "memory_backend": "in-memory",
            "message_limit": config.MESSAGE_TRIM_LIMIT,
        },
        "endpoints": {"chat": "/chat", "health": "/health", "widget": "/widget.js"},
    })


@app.route("/chat", methods=["POST"])
@rate_limit(window_seconds=60)
def chat():
    """Unified endpoint with memory + contract scoping + rate limiting"""

    # --- Input validation ---
    try:
        req_json = request.get_json()
    except Exception as e:
        log_error(ErrorType.VALIDATION_ERROR, "Invalid JSON", context={"error": str(e)}, exception=e)
        return jsonify({"error": "invalid JSON"}), 400

    if not req_json:
        return jsonify({"error": "request body required"}), 400

    # 1. Message
    message = req_json.get("message")
    if not message or not isinstance(message, str):
        return jsonify({"error": "message field is required and must be a string"}), 400

    if len(message) > config.MAX_MESSAGE_LENGTH:
        return jsonify({"error": "message too long", "max_length": config.MAX_MESSAGE_LENGTH}), 400

    message = message.strip()
    if not message:
        return jsonify({"error": "message cannot be empty"}), 400

    # XSS check
    for pattern in ["<script", "javascript:", "onerror=", "onclick=", "<iframe"]:
        if pattern in message.lower():
            return jsonify({"error": "message contains invalid characters"}), 400

    # 2. Context
    context = req_json.get("context", {})
    if not isinstance(context, dict):
        return jsonify({"error": "context must be an object"}), 400

    # 3. User address
    user_address = context.get("user_address")
    if user_address:
        if not isinstance(user_address, str) or not user_address.startswith("0x") or len(user_address) != 42:
            return jsonify({"error": "invalid user_address format"}), 400
        try:
            int(user_address[2:], 16)
        except ValueError:
            return jsonify({"error": "user_address contains invalid characters"}), 400

    # 4. Allowed contracts
    allowed_contract = context.get("allowed_contract")
    allowed_contracts = []

    if allowed_contract:
        raw_list = [allowed_contract] if isinstance(allowed_contract, str) else allowed_contract
        if not isinstance(raw_list, list):
            return jsonify({"error": "allowed_contract must be string or array"}), 400

        for contract in raw_list:
            if not isinstance(contract, str) or not contract.startswith("0x") or len(contract) != 42:
                return jsonify({"error": f"invalid contract format: {contract}"}), 400
            try:
                int(contract[2:], 16)
            except ValueError:
                return jsonify({"error": f"contract contains invalid characters: {contract}"}), 400
            allowed_contracts.append(contract)

    # 5. API key
    api_key = context.get("api_key")
    if api_key:
        if not isinstance(api_key, str) or len(api_key) > 100 or not re.match(r"^[a-zA-Z0-9_-]+$", api_key):
            return jsonify({"error": "invalid api_key"}), 400

    # 6. Conversation ID
    conversation_id = req_json.get("conversation_id")
    if conversation_id:
        if not isinstance(conversation_id, str) or len(conversation_id) > 100:
            return jsonify({"error": "invalid conversation_id"}), 400
        if not re.match(r"^[a-zA-Z0-9_-]+$", conversation_id):
            return jsonify({"error": "invalid conversation_id format"}), 400
    else:
        conversation_id = f"conv_{uuid.uuid4()}"

    # --- Process request ---
    print(f"\n{'#' * 60}")
    print(f"# REQUEST: {message[:100]}{'...' if len(message) > 100 else ''}")
    print(f"# Conversation: {conversation_id}")
    if allowed_contracts:
        print(f"# Scoped to: {allowed_contracts}")
    print(f"{'#' * 60}")

    log_metric("chat_request", 1, context={
        "conversation_id": conversation_id,
        "has_contract_scope": bool(allowed_contracts),
    })

    try:
        result = run_chat_agent(
            message=message,
            user_address=user_address,
            conversation_id=conversation_id,
            allowed_contract=allowed_contracts,
        )
    except Exception as e:
        log_error(
            ErrorType.CHAT_AGENT_FAILURE,
            f"Chat agent failed: {e}",
            context={"conversation_id": conversation_id, "message_preview": message[:100]},
            exception=e,
        )
        return jsonify({
            "conversation_id": conversation_id,
            "response_type": "error",
            "payload": {"message": "Internal error occurred. Please try again."},
        }), 500

    # Security: validate transaction target
    if result["type"] == "transaction":
        tx_target = result["transaction"]["to"].lower()
        if allowed_contracts and tx_target not in [c.lower() for c in allowed_contracts]:
            print(f"[SECURITY] Transaction blocked: {tx_target} not in {allowed_contracts}")
            return jsonify({
                "conversation_id": conversation_id,
                "response_type": "error",
                "payload": {"message": f"Security violation: transaction targets {tx_target} outside allowed scope"},
            }), 403

    print(f"{'#' * 60}\n# COMPLETE - Type: {result['type']}\n{'#' * 60}\n")

    # Build response
    if result["type"] == "transaction":
        return jsonify({
            "conversation_id": conversation_id,
            "response_type": "transaction",
            "payload": {"transaction": result["transaction"], "message": result["message"]},
        })
    elif result["type"] == "error":
        return jsonify({
            "conversation_id": conversation_id,
            "response_type": "error",
            "payload": {"message": result["message"]},
        }), 400
    else:
        return jsonify({
            "conversation_id": conversation_id,
            "response_type": "text",
            "payload": {"message": result["message"]},
        })


if __name__ == "__main__":
    config.print_config()
    app.run(host="0.0.0.0", port=8080, debug=True)
