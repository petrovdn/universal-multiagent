#!/bin/bash
# Start Google Sheets MCP Server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Check if token file exists
TOKEN_PATH="${1:-config/google_sheets_token.json}"

if [ ! -f "$TOKEN_PATH" ]; then
    echo "⚠️  OAuth token not found at $TOKEN_PATH"
    echo "Please enable Google Sheets integration from the Settings panel first."
    echo ""
    echo "The OAuth flow will create the token automatically when you:"
    echo "1. Open the application in your browser"
    echo "2. Click the Settings button (bottom right)"
    echo "3. Enable the Google Sheets toggle"
    echo "4. Complete the Google OAuth authorization"
    exit 1
fi

echo "🚀 Starting Google Sheets MCP Server..."
echo "Token path: $TOKEN_PATH"

python -m src.mcp_servers.google_sheets_server --token-path "$TOKEN_PATH"

