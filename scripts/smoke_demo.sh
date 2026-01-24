#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://127.0.0.1:8000/health/}"
RETRIES=30

for attempt in $(seq 1 "${RETRIES}"); do
  if curl -fsS "${URL}" >/dev/null; then
    echo "Health OK at ${URL}"
    echo "Demo login: demo_premium / demo123"
    exit 0
  fi
  sleep 1
done

echo "Health endpoint not reachable at ${URL}" >&2
exit 1

