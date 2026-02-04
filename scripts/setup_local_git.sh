#!/bin/bash
# Setup local git: pre-commit hook to block forbidden paths.
# Run once after clone. The hook is NOT versioned.
# Usage: ./scripts/setup_local_git.sh
#
# Note: This repo does not track .gitignore. Use a local .gitignore for
# ignored files. Hygiene is enforced by repo_hygiene_check.sh + CI.

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Install pre-commit hook (checks only STAGED files; untracked are ignored)
HOOK="$REPO_ROOT/.git/hooks/pre-commit"
if [ ! -f "$HOOK" ] || ! grep -q "repo_hygiene_check" "$HOOK" 2>/dev/null; then
  cat > "$HOOK" << 'HOOK'
#!/bin/bash
# Local pre-commit: block forbidden paths from being committed (staged only)
set -e
cd "$(git rev-parse --show-toplevel)"
bash scripts/repo_hygiene_check.sh --staged
HOOK
  chmod +x "$HOOK"
  echo "Installed pre-commit hook (checks staged files only)"
fi

echo "Local git setup done."
