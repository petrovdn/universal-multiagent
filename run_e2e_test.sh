#!/bin/bash
# E2E Test Runner
# Запускает E2E тест через WebSocket

echo "🧪 E2E Test Runner"
echo "=================================="
echo ""

# Clear debug log
rm -f .cursor/debug.log 2>/dev/null

# Check if backend is running
echo "📡 Checking backend..."
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Backend is running"
else
    echo "❌ Backend is not running!"
    echo ""
    echo "Start it with: ./restart-server.sh"
    echo "Or: python -m uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000"
    exit 1
fi

echo ""
echo "🚀 Running E2E WebSocket test..."
echo ""

python3 -m pytest tests/test_e2e_websocket.py::TestE2EWebSocket::test_simple_message_returns_final_result -v -s

echo ""
echo "=================================="
echo "📋 Debug log: .cursor/debug.log"
echo ""
echo "View logs with: cat .cursor/debug.log | jq ."
