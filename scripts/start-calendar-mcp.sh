#!/bin/bash
# Start Google Calendar MCP Server
# This script starts the Google Calendar MCP server for handling Calendar operations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Default token path
TOKEN_PATH="${CALENDAR_TOKEN_PATH:-config/google_calendar_token.json}"

# Check if token file exists
if [ ! -f "$TOKEN_PATH" ]; then
    echo "⚠️  OAuth token not found at $TOKEN_PATH"
    echo "Please enable Google Calendar integration from the Settings panel first."
    echo ""
    echo "The OAuth flow will create the token automatically when you:"
    echo "1. Open the application in your browser"
    echo "2. Click the Settings button (bottom right)"
    echo "3. Enable the Google Calendar toggle"
    echo "4. Complete the Google OAuth authorization"
    exit 1
fi

echo "🚀 Starting Google Calendar MCP Server..."
echo "Token path: $TOKEN_PATH"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the Calendar MCP server
python -m src.mcp_servers.google_calendar_server --token-path "$TOKEN_PATH"



