#!/bin/bash
# Test webhook script for SKR Swap bot

URL="http://localhost:4201/webhook"

echo "Testing SKR Swap webhook endpoints..."
echo ""

# Test 1: JSON BUY signal
echo "Test 1: JSON BUY signal"
curl -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d '{"action":"BUY","symbol":"SKR-USDC","amount":10.0,"note":"Test buy signal"}' \
  -w "\n\n"

sleep 1

# Test 2: JSON SELL signal
echo "Test 2: JSON SELL signal"
curl -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d '{"action":"SELL","symbol":"SKR-USDC","amount":10.0,"note":"Test sell signal"}' \
  -w "\n\n"

sleep 1

# Test 3: CSV format (TradingView style)
echo "Test 3: CSV format"
curl -X POST "$URL" \
  -H "Content-Type: text/plain" \
  --data-raw "action=BUY,symbol=SKR-USDC,amount=10.0,note=CSV test" \
  -w "\n\n"

echo "Tests complete!"
echo ""
echo "Check logs at: ./logs/skr-swap.log"
echo "View dashboard at: http://localhost:4201"
