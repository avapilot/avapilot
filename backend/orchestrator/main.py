from flask import Flask, jsonify, request
import uuid

app = Flask(__name__)

@app.route("/chat", methods=['POST'])
def chat():
    """
    Version 1 (Scaffolding): Returns a hardcoded mock ChatResponse 
    containing a TransactionObject, regardless of the input.
    """
    # We generate a conversation_id to simulate the real flow.
    conversation_id = request.json.get('conversation_id') or f"conv_{uuid.uuid4()}"

    # This is our hardcoded transaction object.
    mock_transaction = {
        "to": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4",
        "value": "1000000000000000000", # 1 AVAX in WEI
        "data": "0x00" # Placeholder data for V1
    }

    # This is the full response structure our frontend expects.
    mock_response = {
        "conversation_id": conversation_id,
        "response_type": "transaction",
        "payload": {
            "transaction": mock_transaction
        }
    }

    return jsonify(mock_response)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)
