#!/usr/bin/env bash
set -euo pipefail

# Optional: join the operator's tailnet so apps/ai/client.py can reach a
# self-hosted Ollama instance. Userspace networking because Railway
# containers don't get /dev/net/tun; in-memory state because the
# filesystem is ephemeral anyway and the authkey is reusable.
if [ -n "${TAILSCALE_AUTHKEY:-}" ]; then
  # 2>&1: tailscaled schreibt seinen normalen Status nach stderr, und Railway
  # wertet stderr als Fehler - das verdeckte echte Fehler im Log.
  tailscaled --tun=userspace-networking --socks5-server=localhost:1055 \
    --outbound-http-proxy-listen=localhost:1055 --state=mem: 2>&1 &
  for i in $(seq 1 20); do
    tailscale up --authkey="${TAILSCALE_AUTHKEY}" \
      --hostname="preceptly-railway-${RAILWAY_REPLICA_ID:-1}" \
      --accept-dns=false 2>&1 && break
    sleep 1
  done
fi

python manage.py migrate --noinput

if [ "${DEBUG:-True}" != "True" ] && [ "${DEBUG:-True}" != "true" ]; then
  python manage.py collectstatic --noinput
fi

# Daphne (ASGI) statt Gunicorn (WSGI) – WebSockets benötigen ASGI
exec daphne -b 0.0.0.0 -p ${PORT:-8000} --ping-interval 20 --ping-timeout 10 tutorflow.asgi:application
