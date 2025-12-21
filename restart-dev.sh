#!/bin/bash
# Fig Nodes - Clean Restart Script
# This script cleanly restarts both backend and frontend

set -e  # Exit on error

echo "🧹 Cleaning up old processes..."

# Kill any process on port 8000 (backend)
lsof -ti:8000 | xargs kill -9 2>/dev/null || echo "✓ Port 8000 already free"

# Kill any process on port 5173 (old frontend)
lsof -ti:5173 | xargs kill -9 2>/dev/null || echo "✓ Port 5173 already free"

# Kill any process on port 5174 (React wrapper)
lsof -ti:5174 | xargs kill -9 2>/dev/null || echo "✓ Port 5174 already free"

echo ""
echo "⏳ Waiting for ports to be released..."
sleep 2

echo ""
echo "🚀 Starting backend + old frontend..."
echo "   (This will run in the background)"
echo ""

cd /Users/steve/Fig-Nodes
source .venv/bin/activate

# Start backend in background
nohup uv run python main.py --dev > /tmp/fignodes-backend.log 2>&1 &
BACKEND_PID=$!

echo "   Backend PID: $BACKEND_PID"
echo "   Logs: tail -f /tmp/fignodes-backend.log"
echo ""
echo "⏳ Waiting for backend to start (10 seconds)..."
sleep 10

echo ""
echo "✅ Backend should be running on:"
echo "   - http://localhost:8000 (API)"
echo "   - http://localhost:5173 (Old Frontend)"
echo ""
echo "📝 Next steps:"
echo "   1. In another terminal, run:"
echo "      cd /Users/steve/Fig-Nodes/frontend-react && yarn dev"
echo ""
echo "   2. Visit: http://localhost:5174"
echo ""
echo "🛑 To stop backend:"
echo "   kill $BACKEND_PID"
echo ""

