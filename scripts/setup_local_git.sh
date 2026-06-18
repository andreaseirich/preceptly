#!/bin/bash
# Setup local git: pre-commit hook for hygiene check + auto-formatting.
# Run once after clone. The hook is NOT versioned.
# Usage: ./scripts/setup_local_git.sh
#
# Note: This repo does not track .gitignore. Use a local .gitignore for
# ignored files. Hygiene is enforced by repo_hygiene_check.sh + CI.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Always (re-)install the hook so this script can be used to update it
HOOK="$REPO_ROOT/.git/hooks/pre-commit"
cat > "$HOOK" << 'HOOK'
#!/bin/bash
# Local pre-commit:
#   1. Block forbidden paths (hygiene)
#   2. Auto-format staged Python files with ruff and re-stage them
set -e
cd "$(git rev-parse --show-toplevel)"

# --- Hygiene check ---
bash scripts/repo_hygiene_check.sh --staged

# --- Ruff format ---
if command -v ruff &> /dev/null; then
  # Collect staged Python files that still exist (not deleted)
  STAGED_PY=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
  if [ -n "$STAGED_PY" ]; then
    echo "$STAGED_PY" | xargs ruff format --quiet
    echo "$STAGED_PY" | xargs git add
  fi
else
  echo "Warning: ruff not found – skipping auto-format (run: pip install ruff)"
fi
HOOK
chmod +x "$HOOK"
echo "Installed pre-commit hook (hygiene + ruff format)."

# Install pre-push hook: lint + full Django test suite
PREPUSH="$REPO_ROOT/.git/hooks/pre-push"
cat > "$PREPUSH" << 'HOOK'
#!/bin/bash
# pre-push: lint + Django tests before every push.
# Emergency bypass: git push --no-verify
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
BACKEND="$REPO_ROOT/backend"
export MOCK_LLM=1
export SECRET_KEY=test-ci-secret
export ALLOWED_HOSTS=localhost,127.0.0.1
export DJANGO_SETTINGS_MODULE=tutorflow.settings
export DJANGO_DEBUG=False
echo "╔══════════════════════════════════════╗"
echo "║  pre-push checks (skip: --no-verify) ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "▶ ruff lint..."
if ! ruff check "$BACKEND/apps" "$BACKEND/tutorflow"; then
    echo "✖ Ruff lint failed. Fix before pushing."
    exit 1
fi
echo "✔ lint OK"
echo ""
echo "▶ compile check..."
if ! python3 -m compileall -q "$BACKEND"; then
    echo "✖ Compile error. Fix before pushing."
    exit 1
fi
echo "✔ compile OK"
echo ""
echo "▶ Django tests (this takes ~5 min)..."
if ! (cd "$BACKEND" && python3 manage.py test --verbosity=1 2>&1); then
    echo "✖ Tests failed. Fix before pushing."
    exit 1
fi
echo ""
echo "✔ All checks passed — pushing."
HOOK
chmod +x "$PREPUSH"
echo "Installed pre-push hook (lint + compile + Django tests)."

echo "Local git setup done."
