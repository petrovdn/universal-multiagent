#!/bin/bash

# Start Google Workspace MCP Server
# This script starts the Google Workspace MCP server for testing purposes

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TOKEN_PATH="${PROJECT_ROOT}/config/google_workspace_token.json"
CONFIG_PATH="${PROJECT_ROOT}/config/workspace_config.json"

cd "$PROJECT_ROOT"

if [ ! -f "$TOKEN_PATH" ]; then
    echo "Error: OAuth token not found at $TOKEN_PATH"
    echo "Please enable Google Workspace integration first via the UI"
    exit 1
fi

echo "Starting Google Workspace MCP Server..."
echo "Token: $TOKEN_PATH"
echo "Config: $CONFIG_PATH"

python -m src.mcp_servers.google_workspace_server \
    --token-path "$TOKEN_PATH" \
    --config-path "$CONFIG_PATH"





