#!/bin/bash
# test_message_trimming.sh - FIXED VERSION

echo "🧪 Testing Message Trimming (20-message limit)"
echo "=============================================="

# Create conversation
echo "1️⃣ Creating conversation..."
RESP=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hi, start counting from 1"}')

# Extract conversation_id properly using jq or python
if command -v jq &> /dev/null; then
    CONV_ID=$(echo "$RESP" | jq -r '.conversation_id')
else
    # Fallback: use python
    CONV_ID=$(echo "$RESP" | python3 -c "import sys, json; print(json.load(sys.stdin)['conversation_id'])")
fi

echo "   Conversation ID: $CONV_ID"

if [ -z "$CONV_ID" ] || [ "$CONV_ID" = "null" ]; then
    echo "   ❌ Failed to extract conversation_id"
    echo "   Response was: $RESP"
    exit 1
fi

# Send 25 messages to SAME conversation
echo ""
echo "2️⃣ Sending 25 messages (should trigger trimming)..."

for i in {2..25}; do
    echo -n "   Sending message $i... "
    curl -s -X POST http://localhost:8080/chat \
      -H "Content-Type: application/json" \
      -d "{\"message\": \"Count: $i\", \"conversation_id\": \"$CONV_ID\"}" > /dev/null
    echo "✓"
    sleep 0.5
done

# Check if it remembers early messages
echo ""
echo "3️⃣ Testing memory retention..."

echo -n "   Can it remember message 1? "
RESP1=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"What was the first number I said?\", \"conversation_id\": \"$CONV_ID\"}")

if echo "$RESP1" | grep -qi "\"1\""; then
    echo "YES ⚠️  (should be NO - message 1 should be trimmed!)"
else
    echo "NO ✅ (correct - message 1 was trimmed)"
fi

echo -n "   Can it remember message 10? "
RESP10=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Did I say the number 10?\", \"conversation_id\": \"$CONV_ID\"}")

if echo "$RESP10" | grep -qi "10\|ten\|yes"; then
    echo "YES ⚠️  (should be NO - message 10 should be trimmed!)"
else
    echo "NO ✅ (correct - message 10 was trimmed)"
fi

echo -n "   Can it remember message 20? "
RESP20=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Did I say the number 20?\", \"conversation_id\": \"$CONV_ID\"}")

if echo "$RESP20" | grep -qi "20\|twenty\|yes"; then
    echo "YES ✅ (correct - message 20 is within last 20)"
else
    echo "NO ⚠️  (should be YES - message 20 should be kept!)"
fi

echo ""
echo "✅ Trimming test complete!"
echo ""
echo "Expected behavior:"
echo "- Messages 1-5: Should be FORGOTTEN (trimmed)"
echo "- Messages 6-25: Should be REMEMBERED (last 20)"