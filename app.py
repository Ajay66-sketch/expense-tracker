from flask import Flask, request, redirect, render_template
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = "expenses.db"


# ---------- DATABASE ----------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- HOME ----------
@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()

    # Add new expense
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()

        if title and amount.isdigit() and category:
            conn.execute(
                "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
                (title, int(amount), category, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
        return redirect("/")

    # Fetch expenses and total
    expenses = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
    total = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM expenses").fetchone()[0]

    conn.close()
    return render_template("index.html", expenses=expenses, total=total)


# ---------- EDIT ----------
@app.route("/edit/<int:expense_id>", methods=["POST"])
def edit(expense_id):
    title = request.form.get("title", "").strip()
    amount = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()

    if not (title and amount.isdigit() and category):
        return redirect("/")

    conn = get_db()
    conn.execute(
        "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
        (title, int(amount), category, expense_id),
    )
    conn.commit()
    conn.close()
    return redirect("/")


# ---------- DELETE ----------
@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect("/")


# ---------- RUN SERVER ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
