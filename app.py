from flask import Flask, request, redirect, render_template
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
DB_NAME = "expenses.db"

# ---------- DATABASE ----------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# Auto-create DB if missing (for Render deployment)
if not os.path.exists(DB_NAME):
    conn = get_db()
    conn.execute("""
        CREATE TABLE expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount INTEGER NOT NULL,
            category TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

# ---------- HOME ----------
@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount = request.form.get("amount")
        category = request.form.get("category", "").strip()

        if title and amount and category:
            conn.execute(
                "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
                (title, amount, category, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
        return redirect("/")

    expenses = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
    total = conn.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
    conn.close()
    return render_template("index.html", expenses=expenses, total=total)

# ---------- EDIT ----------
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    title = request.form.get("title", "").strip()
    amount = request.form.get("amount")
    category = request.form.get("category", "").strip()

    if title and amount and category:
        conn = get_db()
        conn.execute(
            "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
            (title, amount, category, id)
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

# ---------- RUN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
