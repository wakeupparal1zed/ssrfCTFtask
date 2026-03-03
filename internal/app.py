import os
import sqlite3

from flask import Flask, request

app = Flask(__name__)

FLAG = os.getenv("FLAG", "practice{default_internal_flag}")
DB_PATH = os.getenv("INTERNAL_DB_PATH", "/tmp/internal.db")


def init_internal_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT NOT NULL,
            password TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flag TEXT NOT NULL
        )
        """
    )
    conn.execute("DELETE FROM admins")
    conn.execute("INSERT INTO admins(login, password) VALUES (?, ?)", ("admin", "super_strong_admin_password"))
    conn.execute("DELETE FROM secrets")
    conn.execute("INSERT INTO secrets(flag) VALUES (?)", (FLAG,))
    conn.commit()
    conn.close()


@app.get("/")
def root():
    return "Service online\n"


@app.get("/admin")
@app.get("/admin/")
def admin_panel():
    login_value = request.args.get("login")
    password_value = request.args.get("password")

    if login_value is None or password_value is None:
        return (
            "<!doctype html>"
            "<html><head><meta charset='utf-8'><title>Admin Login</title></head>"
            "<body>"
            "<h1>Admin Login</h1>"
            "<form method='get' action='/admin'>"
            "<label>Login: <input name='login' type='text'></label><br>"
            "<label>Password: <input name='password' type='password'></label><br>"
            "<button type='submit'>Sign in</button>"
            "</form>"
            "<p></p>"
            "</body></html>"
        )

    conn = sqlite3.connect(DB_PATH)
    query = (
        "SELECT id, login FROM admins "
        f"WHERE login = '{login_value}' AND password = '{password_value}'"
    )

    try:
        row = conn.execute(query).fetchone()
    except sqlite3.Error:
        conn.close()
        return "Internal error\n", 500

    if not row:
        conn.close()
        return "Access denied\n", 403

    flag_row = conn.execute("SELECT flag FROM secrets LIMIT 1").fetchone()
    conn.close()
    flag = flag_row[0] if flag_row else "practice{missing_flag}"
    return f"Welcome, {row[1]}!\nFlag: {flag}\n"


init_internal_db()
