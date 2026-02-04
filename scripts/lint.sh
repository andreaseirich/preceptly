#!/bin/bash
# Linting script for TutorFlow
# Usage: ./scripts/lint.sh

set -euo pipefail

echo "🔍 Running linting checks..."

cd "$(dirname "$0")/.."

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not in a virtual environment. Activate it first:"
    echo "   source venv/bin/activate  # Linux/Mac"
    echo "   venv\\Scripts\\activate     # Windows"
    echo ""
fi

# Check if ruff is installed
if ! command -v ruff &> /dev/null; then
    echo "❌ ruff is not installed. Install it with:"
    echo "   pip install ruff black"
    exit 1
fi

echo "📝 Checking code formatting with ruff format..."
ruff format --check backend/apps backend/tutorflow || {
    echo "❌ Code formatting issues found. Run 'ruff format backend/apps backend/tutorflow' to fix."
    exit 1
}

echo "🔍 Running ruff linter..."
ruff check backend/apps backend/tutorflow || {
    echo "❌ Linting issues found. Run 'ruff check --fix backend/apps backend/tutorflow' to auto-fix some issues."
    exit 1
}

echo "✅ All linting checks passed!"

