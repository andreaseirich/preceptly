#!/bin/bash
# Linting script for TutorFlow
# Usage: ./scripts/lint.sh

set -e

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

echo "🔍 Checking templates for inline scripts/styles..."
# Check for inline scripts, styles, and event handlers
INLINE_ISSUES=0

# Check for <script> tags (excluding external script loading)
if grep -r "<script" backend/apps --include="*.html" | grep -v "{% static" | grep -v "src=" | grep -v "{% endblock %}"; then
    echo "❌ Found inline <script> tags in templates. Move JavaScript to static files."
    INLINE_ISSUES=1
fi

# Check for <style> tags
if grep -r "<style" backend/apps --include="*.html" | grep -v "{% endblock %}"; then
    echo "❌ Found inline <style> tags in templates. Move CSS to static files."
    INLINE_ISSUES=1
fi

# Check for inline event handlers
if grep -rE "(onclick=|onchange=|oninput=|onsubmit=|onload=)" backend/apps --include="*.html"; then
    echo "❌ Found inline event handlers in templates. Use JavaScript event listeners instead."
    INLINE_ISSUES=1
fi

# Check for inline style attributes (allow some exceptions for dynamic content)
# This is a warning, not an error, as some inline styles may be necessary
if grep -r 'style="' backend/apps --include="*.html" | grep -v "{% static" | grep -v "{% endblock %}"; then
    echo "⚠️  Warning: Found inline style attributes. Consider moving to CSS classes where possible."
fi

if [ $INLINE_ISSUES -eq 1 ]; then
    echo "❌ Template inline asset checks failed."
    exit 1
fi

echo "✅ All linting checks passed!"

