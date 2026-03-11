import os
import socket
import sqlite3
from functools import wraps
from urllib.parse import quote, urlparse

import requests
import requests_unixsocket
from flask import (
    Flask,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

WEB_PORT = int(os.getenv("WEB_PORT", "31337"))
WEB_DB_PATH = os.getenv("WEB_DB_PATH", "/tmp/web_users.db")
INTERNAL_SOCKET_PATH = os.getenv("INTERNAL_SOCKET_PATH", "/run/internal/internal.sock")
app.secret_key = os.getenv("SESSION_SECRET", "dev_session_secret_change_me")

ALLOWED_URL_FRAGMENTS = [
    "curl.com",
    "github.com",
]
INTERNAL_HOSTS = {"127.0.0.1", "localhost", "internal", "intra"}


@app.after_request
def disable_cache(resp):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def init_web_db():
    conn = sqlite3.connect(WEB_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            login TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO users(login, password, role) VALUES (?, ?, ?)",
        ("player", "player123", "user"),
    )
    conn.execute(
        "INSERT OR IGNORE INTO users(login, password, role) VALUES (?, ?, ?)",
        ("guest", "guest123", "user"),
    )
    conn.commit()
    conn.close()


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_login" not in session:
            return jsonify({"error": "Login required"}), 401
        return func(*args, **kwargs)

    return wrapper


def is_allowed_by_whitelist(raw_url):
    lowered = raw_url.lower()
    return any(fragment in lowered for fragment in ALLOWED_URL_FRAGMENTS)


def unix_socket_target_url(parsed):
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    encoded_socket = quote(INTERNAL_SOCKET_PATH, safe="")
    return f"http+unix://{encoded_socket}{path}"


@app.get("/")
def index():
    if "user_login" in session:
        return render_template("index.html", user_login=session["user_login"])
    return render_template("login.html")


@app.post("/login")
def login():
    login_value = request.form.get("login", "").strip()
    password_value = request.form.get("password", "").strip()

    if not login_value or not password_value:
        flash("Provide both login and password")
        return redirect(url_for("index"))

    conn = sqlite3.connect(WEB_DB_PATH)
    user = conn.execute(
        "SELECT login FROM users WHERE login = ? AND password = ?",
        (login_value, password_value),
    ).fetchone()
    conn.close()

    if not user:
        flash("Invalid credentials")
        return redirect(url_for("index"))

    session["user_login"] = user[0]
    return redirect(url_for("index"))


@app.post("/register")
def register():
    login_value = request.form.get("login", "").strip()
    password_value = request.form.get("password", "").strip()

    if not login_value or not password_value:
        flash("Provide both login and password")
        return redirect(url_for("index"))

    conn = sqlite3.connect(WEB_DB_PATH)
    try:
        conn.execute(
            "INSERT INTO users(login, password, role) VALUES (?, ?, ?)",
            (login_value, password_value, "user"),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        flash("User already exists")
        return redirect(url_for("index"))

    conn.close()
    flash("User registered, now log in")
    return redirect(url_for("index"))


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.get("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /admin\n", 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.post("/api/fetch")
@app.post("/api/webview")
@login_required
def webview_fetch():
    data = request.get_json(silent=True) or {}
    raw_url = data.get("url", "")

    if not isinstance(raw_url, str) or not raw_url:
        return jsonify({"error": "Pass JSON: {\"url\": \"http://...\"}"}), 400

    if not is_allowed_by_whitelist(raw_url):
        return jsonify({"error": "URL is blocked by whitelist"}), 403

    parsed = urlparse(raw_url)
    if parsed.scheme not in ("http", "https"):
        return jsonify({"error": "Only http/https schemes are supported"}), 400

    upstream_ip = "unknown"
    use_internal_socket = (
        parsed.scheme == "http"
        and parsed.hostname in INTERNAL_HOSTS
        and parsed.port in (None, 80, 5001)
    )

    try:
        if use_internal_socket:
            upstream_ip = "unix-socket"
            session_unix = requests_unixsocket.Session()
            resp = session_unix.get(unix_socket_target_url(parsed), timeout=4)
        else:
            if parsed.hostname:
                try:
                    upstream_ip = socket.gethostbyname(parsed.hostname)
                except Exception:
                    upstream_ip = "unknown"
            resp = requests.get(raw_url, timeout=4)
    except requests.RequestException as exc:
        out = jsonify({"error": f"Upstream request failed: {exc}"})
        out.headers["X-Upstream-IP"] = upstream_ip
        return out, 502

    upstream_content_type = resp.headers.get("Content-Type", "text/plain; charset=utf-8")
    out = make_response(resp.text, resp.status_code)
    out.headers["Content-Type"] = upstream_content_type
    out.headers["X-Upstream-IP"] = upstream_ip
    out.headers["X-Upstream-Content-Type"] = upstream_content_type
    return out


if __name__ == "__main__":
    init_web_db()
    app.run(host="0.0.0.0", port=WEB_PORT)
