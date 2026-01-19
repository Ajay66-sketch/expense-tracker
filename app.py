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

    # Handle adding a new expense
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        amount = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()

        if title and amount and category:
            conn.execute(
                "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
                (title, float(amount), category, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
        return redirect("/")

    # GET request: fetch all expenses and total
    expenses = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
    total = conn.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
    conn.close()
    return render_template("index.html", expenses=expenses, total=total)

# ---------- EDIT ----------
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    title = request.form.get("title", "").strip()
    amount = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()

    if title and amount and category:
        conn = get_db()
        conn.execute(
            "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
            (title, float(amount), category, id)
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

# ---------- RUN APP ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
