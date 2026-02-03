from flask import Flask, request, redirect, render_template, session, Response, url_for
import sqlite3
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "supersecretkey")

DB_NAME = "expenses.db"
IS_PREMIUM = os.getenv("IS_PREMIUM", "false").lower() == "true"
FEATURES = {"export_csv": IS_PREMIUM}

# ---------- DATABASE ----------
def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

init_db()

# ---------- AUTH ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            return render_template("signup.html", error="All fields required")

        hashed = generate_password_hash(password)

        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hashed)
                )
                conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("signup.html", error="Username already exists")

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        try:
            with get_db() as conn:
                user = conn.execute(
                    "SELECT * FROM users WHERE username=?",
                    (username,)
                ).fetchone()
        except sqlite3.OperationalError as e:
            return render_template("login.html", error=f"DB Error: {e}")

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("index"))

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------- HOME ----------
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    user_id = session["user_id"]

    if request.method == "POST":
        title = request.form.get("title")
        amount = request.form.get("amount")
        category = request.form.get("category")

        if title and amount and category:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO expenses
                       (user_id, title, amount, category, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_id, title, float(amount), category,
                     datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                )
                conn.commit()
        return redirect(url_for("index"))

    with get_db() as conn:
        expenses = conn.execute(
            "SELECT * FROM expenses WHERE user_id=? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()

        total = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=?",
            (user_id,)
        ).fetchone()[0]

        category_summary = []
        if IS_PREMIUM:
            category_summary = conn.execute("""
                SELECT category, SUM(amount) AS total
                FROM expenses
                WHERE user_id=?
                GROUP BY category
                ORDER BY total DESC
            """, (user_id,)).fetchall()

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        category_summary=category_summary,
        is_premium=IS_PREMIUM,
        features=FEATURES
    )

# ---------- EDIT ----------
@app.route("/edit/<int:id>", methods=["POST"])
@login_required
def edit(id):
    user_id = session["user_id"]
    title = request.form.get("title")
    amount = request.form.get("amount")
    category = request.form.get("category")

    if title and amount and category:
        with get_db() as conn:
            conn.execute(
                "UPDATE expenses SET title=?, amount=?, category=? WHERE id=? AND user_id=?",
                (title, float(amount), category, id, user_id)
            )
            conn.commit()
    return redirect(url_for("index"))

# ---------- DELETE ----------
@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    user_id = session["user_id"]
    with get_db() as conn:
        conn.execute(
            "DELETE FROM expenses WHERE id=? AND user_id=?",
            (id, user_id)
        )
        conn.commit()
    return redirect(url_for("index"))

# ---------- EXPORT ----------
@app.route("/export")
@login_required
def export_csv():
    if not IS_PREMIUM:
        return "Premium feature 🔒", 403

    user_id = session["user_id"]
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, amount, category, created_at FROM expenses WHERE user_id=?",
            (user_id,)
        ).fetchall()

    def generate():
        yield "id,title,amount,category,created_at\n"
        for r in rows:
            yield f"{r['id']},{r['title']},{r['amount']},{r['category']},{r['created_at']}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"}
    )

if __name__ == "__main__":
    app.run()
