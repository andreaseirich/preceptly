#!/bin/bash
# Repo hygiene: fail if forbidden paths are tracked.
# Used by CI and local pre-commit. No .gitignore or .cursorrules dependency.

set -e

TRACKED=$(git ls-files)
FAIL=0

check() {
  local pattern="$1"
  local msg="$2"
  if echo "$TRACKED" | grep -qE "$pattern"; then
    echo "::error::Forbidden: $msg"
    echo "$TRACKED" | grep -E "$pattern"
    FAIL=1
  fi
}

check '^\.gitignore$' '.gitignore'
check '^\.cursorrules$' '.cursorrules'
check 'cursor_master_prompt\.txt$' 'cursor_master_prompt.txt'
check '^\.cursor/' '.cursor/'
check '^\.vscode/' '.vscode/'
check '^\.idea/' '.idea/'
check '^\.DS_Store$|/\.DS_Store$' '.DS_Store'
check '^Thumbs\.db$|/Thumbs\.db$' 'Thumbs.db'
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
BAD_ENV=$(echo "$TRACKED" | grep -E '^\.env$|/\.env$|^\.env\.' | grep -v '\.env\.example' || true)
if [ -n "$BAD_ENV" ]; then
  echo "::error::Forbidden .env files (only .env.example allowed):"
  echo "$BAD_ENV"
  FAIL=1
fi
check '\.pem$|\.key$|id_rsa|credentials|secrets' 'secrets/keys'
check 'db\.sqlite3$|\.sqlite3$' '*.sqlite3'
check '/media/' 'media/'
check '/uploads/' 'uploads/'
check '^\.githooks/' '.githooks/'

if [ $FAIL -eq 1 ]; then
  exit 1
fi
echo "Repo hygiene OK"
