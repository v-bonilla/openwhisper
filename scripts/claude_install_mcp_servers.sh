#!/bin/bash

set -e

# Install context7 MCP server
echo "Installing context7 MCP server..."
claude mcp add context7 -- npx -y @upstash/context7-mcp

# Install git MCP server
echo "Installing git MCP server..."
claude mcp add git -- uvx mcp-server-git

# Install playwright MCP server
echo "Installing playwright MCP server..."
claude mcp add playwright npx @playwright/mcp@latest

echo ""
echo "All MCP servers installed successfully!"
echo "Run 'claude mcp list' to verify the installation."