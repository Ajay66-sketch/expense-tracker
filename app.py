from flask import Flask, request, redirect, render_template, Response, session, url_for, flash
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Needed for sessions

DB_NAME = "expenses.db"

# ---------------- PREMIUM FLAG ----------------
IS_PREMIUM = os.getenv("IS_PREMIUM", "false").lower() == "true"
FEATURES = {"export_csv": IS_PREMIUM}

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password TEXT NOT NULL
        )
    """)
    # Expenses table
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
    conn.close()

init_db()

# ---------------- LOGIN REQUIRED DECORATOR ----------------
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if username and password:
            conn = get_db()
            try:
                conn.execute(
                    "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                    (username, email, password)
                )
                conn.commit()
                conn.close()
                flash("Account created! Please login.", "success")
                return redirect("/login")
            except sqlite3.IntegrityError:
                flash("Username or Email already exists!", "error")
                conn.close()
    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/")
        else:
            flash("Invalid credentials", "error")
    return render_template("login.html")

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- HOME ----------------
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    conn = get_db()

    if request.method == "POST":
        title = request.form.get("title")
        amount = request.form.get("amount")
        category = request.form.get("category")
        if title and amount and category:
            conn.execute(
                "INSERT INTO expenses (user_id, title, amount, category, created_at) VALUES (?, ?, ?, ?, ?)",
                (session["user_id"], title, float(amount), category, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
        return redirect("/")

    expenses = conn.execute(
        "SELECT * FROM expenses WHERE user_id=? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()

    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id=?",
        (session["user_id"],)
    ).fetchone()[0]

    category_summary = []
    if IS_PREMIUM:
        category_summary = conn.execute("""
            SELECT category, SUM(amount) AS total
            FROM expenses
            WHERE user_id=?
            GROUP BY category
            ORDER BY total DESC
        """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        category_summary=category_summary,
        is_premium=IS_PREMIUM,
        features=FEATURES
    )

# ---------------- EDIT ----------------
@app.route("/edit/<int:id>", methods=["POST"])
@login_required
def edit(id):
    title = request.form.get("title")
    amount = request.form.get("amount")
    category = request.form.get("category")
    if title and amount and category:
        conn = get_db()
        conn.execute(
            "UPDATE expenses SET title=?, amount=?, category=? WHERE id=? AND user_id=?",
            (title, float(amount), category, id, session["user_id"])
        )
        conn.commit()
        conn.close()
    return redirect("/")

# ---------------- DELETE ----------------
@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect("/")

# ---------------- EXPORT CSV (PREMIUM) ----------------
@app.route("/export")
@login_required
def export_csv():
    if not IS_PREMIUM:
        return "Premium feature 🔒", 403

    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, amount, category, created_at FROM expenses WHERE user_id=? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    conn.close()

    def generate():
        yield "id,title,amount,category,created_at\n"
        for r in rows:
            yield f"{r['id']},{r['title']},{r['amount']},{r['category']},{r['created_at']}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"}
    )

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
