"""
Main Flask Application - Single unified endpoint with memory
PRODUCTION READY with input validation
"""

import os
import uuid
import re
import time
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from chat_agent import run_chat_agent
from error_tracker import log_error, log_warning, log_metric, ErrorType
from google.cloud import firestore

# --- Configuration ---
PROJECT_ID = "avapilot" 
os.environ["GCLOUD_PROJECT"] = PROJECT_ID

# Initialize Flask App
app = Flask(__name__)
CORS(app)

# Widget file serving
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


@app.route("/health", methods=['GET'])
def health():
    """Health check endpoint for monitoring"""
    return jsonify({
        "status": "healthy",
        "service": "avapilot-orchestrator",
        "memory": "firestore",
        "message_limit": 20,
        "validation": "enabled"
    })


@app.route("/metrics", methods=['GET'])
def metrics():
    """
    System metrics endpoint for monitoring
    Returns error counts, conversation stats, and system health
    """
    try:
        db = firestore.Client(project=PROJECT_ID)
        
        # Get conversation count (last 24h)
        yesterday = time.time() - 86400
        conversations_ref = db.collection('checkpoints')
        
        # Count recent conversations (approximate)
        # Note: For production, consider maintaining a separate metrics collection
        recent_convs = 0
        try:
            # Sample check - in production, use dedicated metrics
            sample_docs = conversations_ref.limit(100).stream()
            recent_convs = sum(1 for _ in sample_docs)
        except Exception as e:
            log_warning("METRICS_CALCULATION_ERROR", str(e))
        
        return jsonify({
            "status": "healthy",
            "timestamp": int(time.time()),
            "metrics": {
                "conversations_sampled": recent_convs,
                "memory_backend": "firestore",
                "message_limit": 20,
                "error_tracking": "enabled"
            },
            "endpoints": {
                "chat": "/chat",
                "health": "/health",
                "widget": "/widget.js"
            }
        })
        
    except Exception as e:
        log_error(
            ErrorType.API_ERROR,
            f"Metrics endpoint failed: {str(e)}",
            exception=e
        )
        return jsonify({
            "status": "degraded",
            "error": "metrics unavailable"
        }), 500


@app.route("/chat", methods=['POST'])
def chat():
    """
    Unified endpoint with memory + contract scoping + input validation
    """
    # ========================================
    # INPUT VALIDATION
    # ========================================
    
    try:
        req_json = request.get_json()
    except Exception as e:
        log_error(
            ErrorType.VALIDATION_ERROR,
            "Invalid JSON in request",
            context={"error": str(e)},
            exception=e
        )
        return jsonify({"error": "invalid JSON"}), 400
    
    if not req_json:
        return jsonify({"error": "request body required"}), 400
    
    # 1. Validate message
    message = req_json.get("message")
    if not message:
        return jsonify({"error": "message field is required"}), 400
    
    if not isinstance(message, str):
        return jsonify({"error": "message must be a string"}), 400
    
    if len(message) > 2000:
        return jsonify({
            "error": "message too long",
            "max_length": 2000,
            "your_length": len(message)
        }), 400
    
    message = message.strip()
    if len(message) == 0:
        return jsonify({"error": "message cannot be empty"}), 400
    
    # Check for XSS/injection attempts
    suspicious_patterns = ['<script', 'javascript:', 'onerror=', 'onclick=', '<iframe']
    message_lower = message.lower()
    for pattern in suspicious_patterns:
        if pattern in message_lower:
            return jsonify({
                "error": "message contains invalid characters",
                "hint": "HTML/JavaScript not allowed"
            }), 400
    
    # 2. Validate context
    context = req_json.get("context", {})
    if not isinstance(context, dict):
        return jsonify({"error": "context must be an object"}), 400
    
    # 3. Validate user_address
    user_address = context.get("user_address")
    if user_address:
        if not isinstance(user_address, str):
            return jsonify({"error": "user_address must be a string"}), 400
        
        if not user_address.startswith('0x') or len(user_address) != 42:
            return jsonify({
                "error": "invalid user_address format",
                "expected": "0x + 40 hex characters"
            }), 400
        
        try:
            int(user_address[2:], 16)
        except ValueError:
            return jsonify({
                "error": "user_address contains invalid characters"
            }), 400
    
    # 4. Validate allowed_contract
    allowed_contract = context.get("allowed_contract")
    if allowed_contract:
        if not isinstance(allowed_contract, str):
            return jsonify({"error": "allowed_contract must be a string"}), 400
        
        if not allowed_contract.startswith('0x') or len(allowed_contract) != 42:
            return jsonify({
                "error": "invalid allowed_contract format",
                "expected": "0x + 40 hex characters"
            }), 400
        
        try:
            int(allowed_contract[2:], 16)
        except ValueError:
            return jsonify({
                "error": "allowed_contract contains invalid characters"
            }), 400
    
    # 5. Validate API key
    api_key = context.get("api_key")
    if api_key:
        if not isinstance(api_key, str):
            return jsonify({"error": "api_key must be a string"}), 400
        
        if len(api_key) > 100:
            return jsonify({"error": "api_key too long"}), 400
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', api_key):
            return jsonify({
                "error": "api_key contains invalid characters",
                "allowed": "letters, numbers, underscore, hyphen"
            }), 400
    
    # 6. Validate conversation_id
    conversation_id = req_json.get("conversation_id")
    if conversation_id:
        if not isinstance(conversation_id, str):
            return jsonify({"error": "conversation_id must be a string"}), 400
        
        if len(conversation_id) > 100:
            return jsonify({"error": "conversation_id too long"}), 400
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', conversation_id):
            return jsonify({
                "error": "invalid conversation_id format",
                "allowed": "letters, numbers, underscore, hyphen"
            }), 400
    else:
        conversation_id = f"conv_{uuid.uuid4()}"
    
    # ========================================
    # VALIDATION COMPLETE - PROCESS REQUEST
    # ========================================

    print(f"\n{'#'*60}")
    print(f"# REQUEST: {message[:100]}{'...' if len(message) > 100 else ''}")
    print(f"# Conversation: {conversation_id}")
    if allowed_contract:
        print(f"# Scoped to: {allowed_contract}")
    if api_key:
        print(f"# API Key: ***{api_key[-4:] if len(api_key) >= 4 else '***'}")
    print(f"{'#'*60}")
    
    # Log request metric
    log_metric(
        "chat_request",
        1,
        context={
            "conversation_id": conversation_id,
            "has_contract_scope": bool(allowed_contract),
            "has_api_key": bool(api_key)
        }
    )
    
    # Run chat agent with contract restriction
    try:
        result = run_chat_agent(
            message=message,
            user_address=user_address,
            conversation_id=conversation_id,
            allowed_contract=allowed_contract
        )
    except Exception as e:
        log_error(
            ErrorType.CHAT_AGENT_FAILURE,
            f"Chat agent failed: {str(e)}",
            context={
                "conversation_id": conversation_id,
                "message_preview": message[:100],
                "user_address": user_address,
                "allowed_contract": allowed_contract
            },
            exception=e
        )
        return jsonify({
            "conversation_id": conversation_id,
            "response_type": "error",
            "payload": {"message": "Internal error occurred. Please try again."}
        }), 500
    
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
            }), 403
    
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


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080, debug=True)