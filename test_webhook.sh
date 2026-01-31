#!/bin/bash
# Test webhook script for SKR Swap bot

URL="http://localhost:4201/webhook"

echo "Testing SKR Swap webhook endpoints..."
echo ""

# Test 1: Raw BUY signal
echo "Test 1: Raw BUY signal"
curl -X POST "$URL" \
  -H "Content-Type: text/plain" \
  --data-raw "SKR,1m,Gregus,MR-Low,BUY,$(date -u +%Y-%m-%dT%H:%M:%SZ),0.0321" \
  -w "\n\n"

sleep 1

# Test 2: Raw SELL signal
echo "Test 2: Raw SELL signal"
curl -X POST "$URL" \
  -H "Content-Type: text/plain" \
  --data-raw "SKR,1m,Gregus,MR-Low,SELL,$(date -u +%Y-%m-%dT%H:%M:%SZ),0.0321" \
  -w "\n\n"

sleep 1

# Test 3: CSV format with amount override
echo "Test 3: CSV format with amount override"
curl -X POST "$URL" \
  -H "Content-Type: text/plain" \
  --data-raw "signal=SKR,1m,Gregus,MR-Low,BUY,$(date -u +%Y-%m-%dT%H:%M:%SZ),0.0321,amount=10.0,note=CSV test" \
  -w "\n\n"

echo "Tests complete!"
echo ""
echo "Check logs at: ./logs/skr-swap.log"
echo "View dashboard at: http://localhost:4201"
