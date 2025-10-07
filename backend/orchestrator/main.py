from flask import Flask, jsonify, request
from flask_cors import CORS
import uuid

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route("/chat", methods=['POST', 'OPTIONS'])
def chat():
    if request.method == 'OPTIONS':
        # Handle preflight request
        return '', 204
    
    # Handle POST request
    conversation_id = f"conv_{uuid.uuid4()}"
    mock_transaction = {
        "to": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4",
        "value": "1000000000000000000",
        "data": "0x00"
    }
    mock_response = {
        "conversation_id": conversation_id,
        "response_type": "transaction",
        "payload": {"transaction": mock_transaction}
    }
    return jsonify(mock_response)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)