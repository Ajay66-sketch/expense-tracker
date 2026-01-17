from flask import Flask, request, redirect, render_template_string
import sqlite3
from datetime import datetime

app = Flask(__name__)

DB = "expenses.db"

# ---------- Database Helpers ----------

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row  # allows dict-like access
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        amount INTEGER NOT NULL,
        category TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------- HTML Template ----------

HTML = """
<!doctype html>
<html>
<head>
  <title>Expense Tracker</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #f4f7f9;
      padding: 20px;
      max-width: 600px;
      margin: auto;
    }
    h1 { text-align: center; color: #333; }
    form {
      background: #fff;
      padding: 15px;
      border-radius: 8px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.1);
      margin-bottom: 20px;
    }
    input, button {
      padding: 10px;
      margin: 5px 0;
      width: 100%;
      border-radius: 5px;
      border: 1px solid #ccc;
      box-sizing: border-box;
    }
    button {
      background-color: #4CAF50;
      color: white;
      border: none;
      cursor: pointer;
      transition: 0.3s;
    }
    button:hover { background-color: #45a049; }
    table {
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }
    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
    tr:nth-child(even) { background-color: #f9f9f9; }
    .btn-edit { background-color: #FFA500; }
    .btn-edit:hover { background-color: #e59400; }
    .btn-delete { background-color: #f44336; }
    .btn-delete:hover { background-color: #d32f2f; }
    .summary {
      background: #fff;
      padding: 10px;
      border-radius: 8px;
      text-align: center;
      margin-bottom: 20px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.1);
      font-weight: bold;
      color: #333;
    }
  </style>
</head>
<body>
  <h1>Expense Tracker</h1>

  <div class="summary">
    Total Expenses: {{ total }}
  </div>

  <form method="POST" action="/">
    <input type="text" name="title" placeholder="Expense Title" required>
    <input type="number" name="amount" placeholder="Amount" required>
    <input type="text" name="category" placeholder="Category" required>
    <button type="submit">Add Expense</button>
  </form>

  <table>
    <tr>
      <th>Title</th>
      <th>Amount</th>
      <th>Category</th>
      <th>Date</th>
      <th>Actions</th>
    </tr>
    {% for e in expenses %}
    <tr>
      <td>{{ e['title'] }}</td>
      <td>{{ e['amount'] }}</td>
      <td>{{ e['category'] }}</td>
      <td>{{ e['created_at'] }}</td>
      <td>
        <a href="/edit/{{ e['id'] }}"><button class="btn-edit">Edit</button></a>
        <a href="/delete/{{ e['id'] }}"><button class="btn-delete">Delete</button></a>
      </td>
    </tr>
    {% endfor %}
  </table>
</body>
</html>
"""

# ---------- Routes ----------

@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()
    if request.method == "POST":
        title = request.form["title"]
        amount = int(request.form["amount"])
        category = request.form["category"]
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO expenses (title, amount, category, created_at) VALUES (?, ?, ?, ?)",
            (title, amount, category, created_at)
        )
        conn.commit()
    expenses = conn.execute("SELECT * FROM expenses ORDER BY id DESC").fetchall()
    total = sum([e["amount"] for e in expenses])
    conn.close()
    return render_template_string(HTML, expenses=expenses, total=total)

@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit(expense_id):
    conn = get_db()
    expense = conn.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    if not expense:
        conn.close()
        return "Expense not found", 404

    if request.method == "POST":
        conn.execute(
            "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
            (
                request.form["title"],
                int(request.form["amount"]),
                request.form["category"],
                expense_id
            )
        )
        conn.commit()
        conn.close()
        return redirect("/")

    # Render simple edit form
    edit_html = f"""
    <form method="POST">
        <input type="text" name="title" value="{expense['title']}" required>
        <input type="number" name="amount" value="{expense['amount']}" required>
        <input type="text" name="category" value="{expense['category']}" required>
        <button type="submit">Update</button>
    </form>
    """
    conn.close()
    return edit_html

@app.route("/delete/<int:expense_id>")
def delete(expense_id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    conn.commit()
    conn.close()
    return redirect("/")

# ---------- Run ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)


