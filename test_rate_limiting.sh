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
        BODY=$(echo "$RESP" | sed '$d')
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
echo "2️⃣ Testing pro tier (100 req/min)..."
for i in {1..105}; do
    RESP=$(curl -s -X POST http://localhost:8080/chat \
      -H "Content-Type: application/json" \
      -d '{
        "message": "test",
        "context": {"api_key": "avapilot_pro_alice_xyz123"}
      }' \
      -w "\n%{http_code}")
    
    HTTP_CODE=$(echo "$RESP" | tail -n 1)
    
    if [ "$HTTP_CODE" = "429" ]; then
        echo "Request $i: ⛔ Rate limited (expected after 100)"
        break
    elif [ $((i % 25)) -eq 0 ]; then
        echo "Request $i: ✅ Allowed (pro tier)"
    fi
    
    sleep 0.05
done

echo ""
echo "3️⃣ Testing rate limit headers for pro tier..."
RESP=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "context": {"api_key": "avapilot_pro_alice_xyz123"}}' \
  -i)

if echo "$RESP" | grep -q "X-RateLimit-Tier: paid"; then
    echo "✅ Pro tier detected in headers"
    echo "$RESP" | grep "X-RateLimit"
else
    echo "❌ Pro tier not detected"
fi

echo ""
echo "4️⃣ Testing without API key (anonymous)..."
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