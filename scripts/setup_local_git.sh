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

echo "Local git setup done."
