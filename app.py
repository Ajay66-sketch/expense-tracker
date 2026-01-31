from flask import Flask, render_template, request, redirect, Response
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
DB_NAME = "expenses.db"

# ---------- PREMIUM ----------
IS_PREMIUM = os.getenv("IS_PREMIUM", "false").lower() == "true"

# ---------- DATABASE ----------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------- HOME ----------
@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()

    if request.method == "POST":
        title = request.form["title"]
        amount = request.form["amount"]
        category = request.form["category"]

        conn.execute(
            "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
            (title, float(amount), category, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        return redirect("/")

    expenses = conn.execute(
        "SELECT * FROM expenses ORDER BY created_at DESC"
    ).fetchall()

    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses"
    ).fetchone()[0]

    category_summary = []
    if IS_PREMIUM:
        category_summary = conn.execute("""
            SELECT category, SUM(amount) AS total
            FROM expenses
            GROUP BY category
        """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        category_summary=category_summary,
        is_premium=IS_PREMIUM
    )

# ---------- EDIT ----------
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    conn = get_db()
    conn.execute(
        "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
        (
            request.form["title"],
            float(request.form["amount"]),
            request.form["category"],
            id
        )
    )
    conn.commit()
    conn.close()
    return redirect("/")

# ---------- DELETE ----------
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

# ---------- EXPORT CSV (PREMIUM) ----------
@app.route("/export")
def export():
    if not IS_PREMIUM:
        return "Premium feature 🔒", 403

    conn = get_db()
    rows = conn.execute("SELECT * FROM expenses").fetchall()
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

# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
