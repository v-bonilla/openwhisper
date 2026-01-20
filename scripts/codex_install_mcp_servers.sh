#!/bin/bash

set -e

# Install context7 MCP server
echo "Installing context7 MCP server..."
codex mcp add context7 -- npx -y @upstash/context7-mcp

# Install playwright MCP server
echo "Installing playwright MCP server..."
codex mcp add playwright npx @playwright/mcp@latest

echo ""
echo "All MCP servers installed successfully!"
echo "Run 'codex mcp list' to verify the installation."
