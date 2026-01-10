from flask import Flask, request, redirect, render_template_string
import sqlite3
from datetime import datetime

app = Flask(__name__)

# ---------- Database ----------

DB = "expenses.db"

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row  # So we can access columns by name
    return conn

def init_db():
    """Create the expenses table if it doesn't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                amount INTEGER NOT NULL,
                category TEXT,
                created_at TEXT NOT NULL
            )
        """)

init_db()  # Initialize DB at startup

# ---------- Helpers ----------

def read_expenses():
    with get_db() as conn:
        cursor = conn.execute("SELECT * FROM expenses ORDER BY created_at DESC")
        return cursor.fetchall()

def add_expense(title, amount, category):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
            (title, amount, category, datetime.now().isoformat())
        )

def update_expense(expense_id, title, amount, category):
    with get_db() as conn:
        conn.execute(
            "UPDATE expenses SET title = ?, amount = ?, category = ? WHERE id = ?",
            (title, amount, category, expense_id)
        )

def delete_expense(expense_id):
    with get_db() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))

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
    <input type="text" name="category" placeholder="Category">
    <button type="submit">Add Expense</button>
  </form>

  <h3>Expenses</h3>
  {% for e in expenses %}
    <div class="expense">
      <span>{{ e['title'] }} ({{ e['category'] }}) - ₹{{ e['amount'] }}</span>
      <span class="btn"><a href="/edit/{{ e['id'] }}">Edit</a></span>
      <span class="btn"><a href="/delete/{{ e['id'] }}">Delete</a></span>
    </div>
  {% else %}
    <p>No expenses yet.</p>
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
  <form method="POST">
    <input type="text" name="title" value="{{ e['title'] }}" required>
    <input type="number" name="amount" value="{{ e['amount'] }}" required>
    <input type="text" name="category" value="{{ e['category'] }}">
    <button type="submit">Update</button>
  </form>
  <a href="/">Cancel</a>
</body>
</html>
"""

# ---------- Routes ----------

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        title = request.form["title"]
        amount = int(request.form["amount"])
        category = request.form["category"]
        add_expense(title, amount, category)
        return redirect("/")
    expenses = read_expenses()
    return render_template_string(HTML, expenses=expenses)

@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit(expense_id):
    expenses = read_expenses()
    expense = next((e for e in expenses if e['id'] == expense_id), None)
    if not expense:
        return redirect("/")
    if request.method == "POST":
        title = request.form["title"]
        amount = int(request.form["amount"])
        category = request.form["category"]
        update_expense(expense_id, title, amount, category)
        return redirect("/")
    return render_template_string(EDIT_HTML, e=expense)

@app.route("/delete/<int:expense_id>")
def delete(expense_id):
    delete_expense(expense_id)
    return redirect("/")

# ---------- Run ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)





