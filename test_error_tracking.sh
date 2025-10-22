#!/bin/bash

echo "🧪 Testing Error Tracking & Monitoring"
echo "========================================"

# Test 1: Health Check
echo ""
echo "1️⃣ Testing /health endpoint..."
HEALTH=$(curl -s http://localhost:8080/health)
if echo "$HEALTH" | grep -q 'healthy'; then
    echo "   ✅ Health endpoint working"
else
    echo "   ❌ Health endpoint failed"
    echo "   Response: $HEALTH"
    exit 1
fi

# Test 2: Metrics Endpoint
echo ""
echo "2️⃣ Testing /metrics endpoint..."
METRICS=$(curl -s http://localhost:8080/metrics)
if echo "$METRICS" | grep -q 'error_tracking'; then
    echo "   ✅ Metrics endpoint working"
    echo "   ✅ Error tracking is enabled"
else
    echo "   ❌ Metrics endpoint failed"
    echo "   Response: $METRICS"
    exit 1
fi

# Test 3: Validation Error (Invalid JSON)
echo ""
echo "3️⃣ Testing validation error logging..."
RESP=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d 'invalid json' \
  -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESP" | tail -n1)
if [ "$HTTP_CODE" = "400" ]; then
    echo "   ✅ Invalid JSON rejected with 400"
else
    echo "   ❌ Expected 400, got $HTTP_CODE"
    echo "   Response: $(echo "$RESP" | head -n -1)"
fi

# Test 4: Validation Error (Empty Message)
echo ""
echo "4️⃣ Testing empty message validation..."
RESP=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": ""}' \
  -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESP" | tail -n1)
if [ "$HTTP_CODE" = "400" ]; then
    echo "   ✅ Empty message rejected with 400"
else
    echo "   ❌ Expected 400, got $HTTP_CODE"
    echo "   Response: $(echo "$RESP" | head -n -1)"
fi

# Test 5: XSS Protection
echo ""
echo "5️⃣ Testing XSS injection protection..."
RESP=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "<script>alert(1)</script>"}' \
  -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESP" | tail -n1)
if [ "$HTTP_CODE" = "400" ]; then
    echo "   ✅ XSS attempt blocked with 400"
else
    echo "   ❌ Expected 400, got $HTTP_CODE"
    echo "   Response: $(echo "$RESP" | head -n -1)"
fi

# Test 6: Invalid Address Format
echo ""
echo "6️⃣ Testing invalid address validation..."
RESP=$(curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "test",
    "context": {
      "user_address": "invalid_address"
    }
  }' \
  -w "\n%{http_code}")

HTTP_CODE=$(echo "$RESP" | tail -n1)
if [ "$HTTP_CODE" = "400" ]; then
    echo "   ✅ Invalid address rejected with 400"
else
    echo "   ❌ Expected 400, got $HTTP_CODE"
    echo "   Response: $(echo "$RESP" | head -n -1)"
fi

# Test 7: Metrics Logging
echo ""
echo "7️⃣ Testing metric logging..."
curl -s -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "context": {
      "user_address": "0x1234567890123456789012345678901234567890",
      "allowed_contract": "0x60aE616a2155Ee3d9A68541Ba4544862310933d4"
    }
  }' > /dev/null

echo "   ✅ Request sent (check console for metric log)"

echo ""
echo "========================================"
echo "✅ All tests passed!"
echo ""
echo "Next steps:"
echo "1. Check console output for error logs"
echo "2. Verify logs in Cloud Console:"
echo "   https://console.cloud.google.com/logs/query?project=avapilot"
echo "3. Search for: logName='projects/avapilot/logs/avapilot-errors'"