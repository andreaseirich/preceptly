#!/bin/bash
# Setup local git: pre-commit hook to block forbidden paths.
# Run once after clone. The hook is NOT versioned.
# Usage: ./scripts/setup_local_git.sh
#
# Note: This repo does not track .gitignore. Use a local .gitignore for
# ignored files. Hygiene is enforced by repo_hygiene_check.sh + CI.

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Install pre-commit hook
HOOK="$REPO_ROOT/.git/hooks/pre-commit"
if [ ! -f "$HOOK" ] || ! grep -q "repo_hygiene_check" "$HOOK" 2>/dev/null; then
  cat > "$HOOK" << 'HOOK'
#!/bin/bash
# Local pre-commit: block forbidden paths (not versioned)
set -e
cd "$(git rev-parse --show-toplevel)"
bash scripts/repo_hygiene_check.sh
HOOK
  chmod +x "$HOOK"
  echo "Installed pre-commit hook"
fi

echo "Local git setup done."
