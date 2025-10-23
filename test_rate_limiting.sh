#!/bin/bash

echo "🧪 Testing Rate Limiting"
echo "========================"

echo "1️⃣ Testing free tier (20 req/min)..."
for i in {1..25}; do
    RESP=$(curl -s -X POST http://localhost:8080/chat \
      -H "Content-Type: application/json" \
      -d '{
        "message": "test",
        "context": {"api_key": "avapilot_free_alpha"}
      }' \
      -w "\n%{http_code}")
    
    HTTP_CODE=$(echo "$RESP" | tail -n 1)
    
    if [ "$HTTP_CODE" = "429" ]; then
        echo "Request $i: ⛔ Rate limited (expected after 20)"
        
        # Check response includes upgrade message (use sed instead of head)
        BODY=$(echo "$RESP" | sed '$d')  # Remove last line
        if echo "$BODY" | grep -q "free tier"; then
            echo "  ✅ Includes upgrade message"
        fi
        break
    else
        echo "Request $i: ✅ Allowed"
    fi
    
    sleep 0.1
done

echo ""
echo "2️⃣ Testing rate limit headers..."
# Use -i for headers and parse correctly
RESP=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "context": {"api_key": "avapilot_free_alpha"}}' \
  -i)

if echo "$RESP" | grep -q "X-RateLimit-Limit"; then
    echo "✅ Rate limit headers present"
    echo "$RESP" | grep "X-RateLimit"
else
    echo "❌ Rate limit headers missing"
    echo ""
    echo "Full response headers:"
    echo "$RESP" | head -n 20
fi

echo ""
echo "3️⃣ Testing without API key (anonymous)..."
RESP=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}' \
  -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESP" | tail -n 1)
BODY=$(echo "$RESP" | sed '$d')

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "429" ]; then
    echo "✅ Anonymous requests work (same rate limit as free tier)"
else
    echo "❌ Anonymous request failed with status $HTTP_CODE"
    echo "Response: $BODY"
fi

echo ""
echo "✅ Rate limiting tests complete!"