#!/bin/bash
# Start Gmail MCP Server
# This script starts the Gmail MCP server for handling Gmail operations

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Default token path
TOKEN_PATH="${GMAIL_TOKEN_PATH:-config/gmail_token.json}"

echo "Starting Gmail MCP Server..."
echo "Token path: $TOKEN_PATH"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run the Gmail MCP server
python -m src.mcp_servers.gmail_server --token-path "$TOKEN_PATH"

