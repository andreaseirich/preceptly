#!/bin/bash
# Setup local git: exclude patterns + pre-commit hook.
# Run once after clone. These files are NOT versioned.
# Usage: ./scripts/setup_local_git.sh

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Append exclude patterns to .git/info/exclude (if not already present)
EXCLUDE="$REPO_ROOT/.git/info/exclude"
MARKER="# tutorflow hygiene - add forbidden patterns"
if ! grep -q "$MARKER" "$EXCLUDE" 2>/dev/null; then
  echo "" >> "$EXCLUDE"
  echo "$MARKER" >> "$EXCLUDE"
  cat >> "$EXCLUDE" << 'EXCL'
.cursor/
.cursorrules
.gitignore
.vscode/
.idea/
.DS_Store
Thumbs.db
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
node_modules/
.next/
dist/
build/
coverage/
*.log
*.tmp
*.swp
.env
.env.*
!.env.example
*.pem
*.key
db.sqlite3
*.sqlite3
media/
uploads/
.githooks/
EXCL
  echo "Added exclude patterns to .git/info/exclude"
fi

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
