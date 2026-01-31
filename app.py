from flask import Flask, request, redirect, render_template, Response
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ----------------
@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()

    if request.method == "POST":
        title = request.form.get("title")
        amount = request.form.get("amount")
        category = request.form.get("category")

        if title and amount and category:
            conn.execute(
                "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
                (
                    title,
                    float(amount),
                    category,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
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
        category_summary = conn.execute(
            """
            SELECT category, SUM(amount) AS total
            FROM expenses
            GROUP BY category
            ORDER BY total DESC
            """
        ).fetchall()

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
def edit(id):
    title = request.form.get("title")
    amount = request.form.get("amount")
    category = request.form.get("category")

    if title and amount and category:
        conn = get_db()
        conn.execute(
            "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
            (title, float(amount), category, id)
        )
        conn.commit()
        conn.close()

    return redirect("/")

# ---------------- DELETE ----------------
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

# ---------------- EXPORT CSV (PREMIUM) ----------------
@app.route("/export")
def export_csv():
    if not IS_PREMIUM:
        return "Premium feature 🔒", 403

    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, amount, category, created_at FROM expenses ORDER BY created_at DESC"
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
