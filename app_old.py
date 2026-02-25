from flask import Flask, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "expenses.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        amount = request.form["amount"]
        category = request.form["category"]
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cur.execute(
            "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
            (title, amount, category, created_at),
        )
        conn.commit()
        return redirect(url_for("index"))

    cur.execute("SELECT * FROM expenses ORDER BY id DESC")
    expenses = cur.fetchall()
    conn.close()

    return """
    <h2>Expense Tracker</h2>

    <form method="post">
        <input name="title" placeholder="Title" required>
        <input name="amount" type="number" placeholder="Amount" required>
        <input name="category" placeholder="Category" required>
        <button>Add</button>
    </form>

    <hr>

    <ul>
    """ + "".join(
        f"""
        <li>
            {e['title']} | ₹{e['amount']} | {e['category']} | {e['created_at']}
            <a href="/edit/{e['id']}">Edit</a>
            <a href="/delete/{e['id']}">Delete</a>
        </li>
        """ for e in expenses
    ) + "</ul>"

@app.route("/delete/<int:id>")
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("index"))

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        amount = request.form["amount"]
        category = request.form["category"]

        cur.execute(
            "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
            (title, amount, category, id),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    cur.execute("SELECT * FROM expenses WHERE id=?", (id,))
    e = cur.fetchone()
    conn.close()

    return f"""
    <h2>Edit Expense</h2>
    <form method="post">
        <input name="title" value="{e['title']}" required>
        <input name="amount" type="number" value="{e['amount']}" required>
        <input name="category" value="{e['category']}" required>
        <button>Update</button>
    </form>
    <a href="/">Back</a>
    """

if __name__ == "__main__":
    app.run(debug=True)











