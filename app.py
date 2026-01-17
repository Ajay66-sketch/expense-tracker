from flask import Flask, request, redirect, render_template_string
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

DB = "expenses.db"

# ---------- HTML Templates ----------

HTML = """
<!doctype html>
<html>
<head>
  <title>Expense Tracker</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: Arial; padding: 15px; max-width: 500px; margin: auto; }
    input, button { padding: 8px; margin: 3px 0; width: 100%; }
    .expense { display: flex; justify-content: space-between; margin-bottom: 5px; }
    .expense span { flex: 1; }
    .btn { flex: 0 0 auto; margin-left: 5px; }
  </style>
</head>
<body>
  <h2>Expense Tracker</h2>
  <form method="POST" action="/">
    <input type="text" name="title" placeholder="Title" required>
    <input type="number" name="amount" placeholder="Amount" required>
    <input type="text" name="category" placeholder="Category" required>
    <button type="submit">Add Expense</button>
  </form>
  <hr>
  {% for e in expenses %}
    <div class="expense">
      <span>{{ e[1] }} | {{ e[2] }} | {{ e[3] }}</span>
      <a class="btn" href="/edit/{{ e[0] }}">Edit</a>
      <a class="btn" href="/delete/{{ e[0] }}">Delete</a>
    </div>
  {% endfor %}
</body>
</html>
"""

EDIT_HTML = """
<!doctype html>
<html>
<head>
  <title>Edit Expense</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body>
  <h2>Edit Expense</h2>
  <form method="POST" action="/edit/{{ e[0] }}">
    <input type="text" name="title" value="{{ e[1] }}" required>
    <input type="number" name="amount" value="{{ e[2] }}" required>
    <input type="text" name="category" value="{{ e[3] }}" required>
    <button type="submit">Update</button>
  </form>
</body>
</html>
"""

# ---------- Database Helpers ----------

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB):
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
        print("Database created successfully.")

# ---------- Routes ----------

@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()
    if request.method == "POST":
        title = request.form["title"]
        amount = int(request.form["amount"])
        category = request.form["category"]
        created_at = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
            (title, amount, category, created_at)
        )
        conn.commit()
    cur = conn.execute("SELECT * FROM expenses ORDER BY created_at DESC")
    expenses = cur.fetchall()
    conn.close()
    return render_template_string(HTML, expenses=expenses)

@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit(expense_id):
    conn = get_db()
    if request.method == "POST":
        title = request.form["title"]
        amount = int(request.form["amount"])
        category = request.form["category"]
        conn.execute(
            "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
            (title, amount, category, expense_id)
        )
        conn.commit()
        conn.close()
        return redirect("/")
    else:
        cur = conn.execute("SELECT * FROM expenses WHERE id=?", (expense_id,))
        expense = cur.fetchone()
        conn.close()
        if expense:
            return render_template_string(EDIT_HTML, e=expense)
        else:
            return "Expense not found", 404

@app.route("/delete/<int:expense_id>")
def delete(expense_id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect("/")

# ---------- Main ----------

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", debug=False)

