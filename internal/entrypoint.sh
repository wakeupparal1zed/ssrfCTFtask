#!/bin/sh
set -eu

SOCKET_PATH="${INTERNAL_SOCKET_PATH:-/run/internal/internal.sock}"
rm -f "$SOCKET_PATH"

exec gunicorn \
  --bind "unix:${SOCKET_PATH}" \
  --workers 1 \
  --threads 2 \
  --timeout 30 \
  app:app
