#!/bin/bash
# Repo hygiene: fail if forbidden paths are tracked or staged.
# Usage:
#   bash scripts/repo_hygiene_check.sh        # CI: check all tracked files
#   bash scripts/repo_hygiene_check.sh --staged   # Pre-commit: check only staged files
# No .gitignore dependency; untracked files are ignored.

set -e

STAGED=false
if [ "${1:-}" = "--staged" ]; then
  STAGED=true
fi

if [ "$STAGED" = true ]; then
  FILES=$(git diff --cached --name-only)
  SCOPE="staged"
else
  FILES=$(git ls-files)
  SCOPE="tracked"
fi

FAIL=0

check() {
  local pattern="$1"
  local msg="$2"
  local hits
  hits=$(echo "$FILES" | grep -E "$pattern" || true)
  if [ -n "$hits" ]; then
    echo "::error::Forbidden ($SCOPE): $msg"
    echo "$hits"
    FAIL=1
  fi
}

check '^\.gitignore$' '.gitignore'
check '^\.cursorrules$' '.cursorrules'
check 'cursor_master_prompt\.txt$' 'cursor_master_prompt.txt'
check '^\.cursor/' '.cursor/'
check '^\.vscode/' '.vscode/'
check '^\.idea/' '.idea/'
check '\.DS_Store$' '.DS_Store'
check 'Thumbs\.db$' 'Thumbs.db'
check '__pycache__/' '__pycache__/'
check '\.pytest_cache/' '.pytest_cache'
check '\.mypy_cache/' '.mypy_cache'
check '\.ruff_cache/' '.ruff_cache'
check 'node_modules/' 'node_modules/'
check '^\.next/' '.next/'
check '/dist/' 'dist/'
check '/build/' 'build/'
check 'coverage/' 'coverage/'
check '\.coverage' '.coverage'
check 'htmlcov/' 'htmlcov/'
check '\.log$' '*.log'
check '\.tmp$|\.swp$' '*.tmp, *.swp'

# .env, .env.*, secrets.* (allow .env.example only)
BAD_ENV=$(echo "$FILES" | grep -E '^\.env$|/\.env$|\.env\.' | grep -v '\.env\.example' || true)
if [ -n "$BAD_ENV" ]; then
  echo "::error::Forbidden ($SCOPE): .env files (only .env.example allowed)"
  echo "$BAD_ENV"
  FAIL=1
fi
BAD_SECRETS=$(echo "$FILES" | grep -E 'secrets\.|/secrets/' || true)
if [ -n "$BAD_SECRETS" ]; then
  echo "::error::Forbidden ($SCOPE): secrets files"
  echo "$BAD_SECRETS"
  FAIL=1
fi

check '\.pem$|\.key$|id_rsa|credentials' 'secrets/keys'
check '\.sqlite3$' '*.sqlite3'
check '/media/' 'media/'
check '/uploads/' 'uploads/'
check '^\.githooks/' '.githooks/'
check 'venv/|/venv/' 'venv/'
check '\.venv/' '.venv/'

if [ $FAIL -eq 1 ]; then
  echo ""
  echo "Remove these paths from the index: git rm --cached <path>"
  echo "Or unstage: git reset HEAD <path>"
  exit 1
fi
echo "Repo hygiene OK"
