#!/bin/bash

# Hook to format Python files with ruff after Edit/Write operations
# Reads stdin (JSON from PostToolUse hook) and formats .py/.ipynb files

# Extract file_path from JSON input
file_path=$(jq -r '.tool_input.file_path')

# Check if the file is a Python file
if echo "$file_path" | grep -qE '\.py$|\.ipynb$'; then
    ruff check --fix --exit-zero "$file_path" && ruff format "$file_path"
fi
