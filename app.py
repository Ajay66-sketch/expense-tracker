from flask import Flask, render_template, request, redirect, url_for, session, Response, flash
import sqlite3
from datetime import datetime
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # required for sessions & flash messages

DB_NAME = "expenses.db"

# Premium flag
IS_PREMIUM = os.getenv("IS_PREMIUM", "false").lower() == "true"
FEATURES = {"export_csv": IS_PREMIUM}

# ---------------- Database ----------------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
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
    conn.close()

init_db()

# ---------------- Auth ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username and password:
            hashed_pw = generate_password_hash(password)
            try:
                conn = get_db()
                conn.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hashed_pw)
                )
                conn.commit()
                conn.close()
                flash("Account created! Please login.", "success")
                return redirect("/login")
            except sqlite3.IntegrityError:
                flash("Username already exists!", "danger")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        ).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect("/")
        else:
            flash("Invalid username or password", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- Home ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "user_id" not in session:
        return redirect("/login")

    user_id = session["user_id"]
    conn = get_db()

    # Add expense
    if request.method == "POST":
        title = request.form.get("title")
        amount = request.form.get("amount")
        category = request.form.get("category")
        if title and amount and category:
            conn.execute(
                "INSERT INTO expenses (user_id, title, amount, category, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, title, float(amount), category, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
        return redirect("/")

    # Fetch expenses
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

    conn.close()
    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        category_summary=category_summary,
        is_premium=IS_PREMIUM,
        features=FEATURES
    )

# ---------------- Edit/Delete ----------------
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    if "user_id" not in session:
        return redirect("/login")

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

@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect("/")

# ---------------- Export CSV ----------------
@app.route("/export")
def export_csv():
    if not IS_PREMIUM:
        return "Premium feature 🔒", 403
    if "user_id" not in session:
        return redirect("/login")

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

# ---------------- Run ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
