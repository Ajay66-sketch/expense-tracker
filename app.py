from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = "expenses.db"


# ---------- DB ----------
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- HOME ----------
@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()

    if request.method == "POST":
        title = request.form["title"].strip()
        amount = request.form["amount"]
        category = request.form["category"].strip()

        if title and amount and category:
            conn.execute(
                """
                INSERT INTO expenses (title, amount, category, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (title, amount, category, datetime.now().strftime("%Y-%m-%d %H:%M")),
            )
            conn.commit()

        return redirect(url_for("index"))

    expenses = conn.execute(
        "SELECT * FROM expenses ORDER BY id DESC"
    ).fetchall()

    total = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses"
    ).fetchone()[0]

    conn.close()
    return render_template("index.html", expenses=expenses, total=total)


# ---------- EDIT ----------
@app.route("/edit/<int:id>", methods=["POST"])
def edit(id):
    title = request.form["title"]
    amount = request.form["amount"]
    category = request.form["category"]

    conn = get_db()
    conn.execute(
        "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
        (title, amount, category, id),
    )
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


# ---------- DELETE ----------
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
