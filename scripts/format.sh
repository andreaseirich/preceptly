#!/bin/bash
# Auto-format script for TutorFlow
# Usage: ./scripts/format.sh

set -e

echo "📝 Formatting code with ruff..."

cd "$(dirname "$0")/.."

# Check if ruff is installed
if ! command -v ruff &> /dev/null; then
    echo "❌ ruff is not installed. Install it with:"
    echo "   pip install ruff"
    exit 1
fi

# Format all Python files
echo "Formatting backend/apps and backend/tutorflow..."
ruff format backend/apps backend/tutorflow

echo "✅ Code formatting complete!"
