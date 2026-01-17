from flask import Flask, request, redirect, render_template_string, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

DB = "expenses.db"

# ---------- Database Helpers ----------

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
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
    body { font-family: 'Segoe UI', Tahoma, Geneva, sans-serif; margin: 0; padding: 20px; background: #f4f7f8; color: #333; }
    h1 { text-align: center; color: #2c3e50; }
    .container { max-width: 900px; margin: auto; background: #fff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }

    .total { text-align: center; font-size: 1.5em; font-weight: bold; margin-bottom: 20px; color: #e74c3c; }

    form { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 20px; }
    form input, form select, form button { flex: 1 1 100%; padding: 10px; font-size: 1em; border-radius: 6px; border: 1px solid #ccc; }
    form button { background-color: #3498db; color: white; border: none; cursor: pointer; transition: background 0.3s; }
    form button:hover { background-color: #2980b9; }

    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { padding: 12px 10px; text-align: left; border-bottom: 1px solid #ddd; }
    th { background-color: #3498db; color: white; text-transform: uppercase; }
    tr:nth-child(even) { background-color: #f9f9f9; }
    tr:hover { background-color: #f1f1f1; }

    .btn { padding: 6px 12px; border-radius: 6px; border: none; cursor: pointer; font-size: 0.9em; text-decoration: none; display: inline-block; }
    .btn-edit { background-color: #f39c12; color: white; }
    .btn-edit:hover { background-color: #e67e22; }
    .btn-delete { background-color: #e74c3c; color: white; }
    .btn-delete:hover { background-color: #c0392b; }

    @media (min-width: 600px) {
      form input, form select { flex: 1 1 calc(33% - 10px); }
      form button { flex: 1 1 calc(33% - 10px); }
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Expense Tracker</h1>
    <div class="total">
      Total Expenses: {{ total }}
    </div>

    <form method="POST" action="/">
      <input type="text" name="title" placeholder="Expense Title" required>
      <input type="number" name="amount" placeholder="Amount" required min="0">
      <input type="text" name="category" placeholder="Category" required>
      <button type="submit">Add Expense</button>
    </form>

    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Amount</th>
          <th>Category</th>
          <th>Date</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {% for e in expenses %}
        <tr>
          <td>{{ e.title }}</td>
          <td>{{ e.amount }}</td>
          <td>{{ e.category }}</td>
          <td>{{ e.created_at }}</td>
          <td>
            <a class="btn btn-edit" href="/edit/{{ e.id }}">Edit</a>
            <a class="btn btn-delete" href="/delete/{{ e.id }}" onclick="return confirm('Are you sure you want to delete this expense?');">Delete</a>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
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
    cur = conn.cursor()
    cur.execute("SELECT * FROM expenses ORDER BY id DESC")
    expenses = cur.fetchall()
    total = sum([e["amount"] for e in expenses])
    conn.close()
    return render_template_string(HTML, expenses=expenses, total=total)

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM expenses WHERE id=?", (id,))
    expense = cur.fetchone()
    if not expense:
        conn.close()
        return redirect("/")
    if request.method == "POST":
        title = request.form["title"]
        amount = int(request.form["amount"])
        category = request.form["category"]
        cur.execute(
            "UPDATE expenses SET title=?, amount=?, category=? WHERE id=?",
            (title, amount, category, id)
        )
        conn.commit()
        conn.close()
        return redirect("/")
    conn.close()
    # Inline edit form
    return render_template_string("""
    <form method="POST">
      <input type="text" name="title" value="{{ expense.title }}" required>
      <input type="number" name="amount" value="{{ expense.amount }}" required>
      <input type="text" name="category" value="{{ expense.category }}" required>
      <button type="submit">Save Changes</button>
    </form>
    """, expense=expense)

@app.route("/delete/<int:id>")
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM expenses WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

# ---------- Run ----------

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False)



