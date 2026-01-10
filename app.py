from flask import Flask, request, redirect, render_template_string
import csv
import os
from datetime import datetime

app = Flask(__name__)
FILE = "expenses.csv"

# ---------- Helpers ----------

def read_expenses():
    expenses = []
    if os.path.exists(FILE):
        with open(FILE, newline="") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) == 4:
                    expenses.append(row)
    return expenses


def write_expenses(expenses):
    with open(FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(expenses)

# ---------- HTML ----------

HTML = """
<!doctype html>
<html>
<head>
  <title>Expense Tracker</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: Arial; padding: 15px; max-width: 500px; margin: auto; }
    input, button { padding: 8px; margin: 4px 0; width: 100%; }
    .expense { display: flex; justify-content: space-between; margin-bottom: 5px; }
    .btn { margin-left: 5px; }
    a { text-decoration: none; }
  </style>
</head>
<body>

<h2>Add Expense</h2>
<form method="post">
  <input name="title" placeholder="Title" required>
  <input name="amount" type="number" placeholder="Amount" required>
  <input name="category" placeholder="Category" required>
  <button>Add</button>
</form>

<h2>Expenses</h2>
{% for e in expenses %}
<div class="expense">
  <span>{{e[1]}} | ₹{{e[2]}} | {{e[3]}}</span>
  <span>
    <a class="btn" href="/edit/{{e[0]}}">Edit</a>
    <a class="btn" href="/delete/{{e[0]}}">Delete</a>
  </span>
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
<form method="post">
  <input name="title" value="{{e[1]}}" required>
  <input name="amount" type="number" value="{{e[2]}}" required>
  <input name="category" value="{{e[3]}}" required>
  <button>Update</button>
</form>

<a href="/">Cancel</a>

</body>
</html>
"""

# ---------- Routes ----------

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        expense_id = str(int(datetime.now().timestamp()))
        title = request.form["title"]
        amount = request.form["amount"]
        category = request.form["category"]

        with open(FILE, "a", newline="") as f:
            csv.writer(f).writerow([expense_id, title, amount, category])

        return redirect("/")

    return render_template_string(HTML, expenses=read_expenses())


@app.route("/edit/<expense_id>", methods=["GET", "POST"])
def edit(expense_id):
    expenses = read_expenses()

    for i, e in enumerate(expenses):
        if e[0] == expense_id:
            if request.method == "POST":
                expenses[i] = [
                    expense_id,
                    request.form["title"],
                    request.form["amount"],
                    request.form["category"]
                ]
                write_expenses(expenses)
                return redirect("/")

            return render_template_string(EDIT_HTML, e=e)

    return redirect("/")


@app.route("/delete/<expense_id>")
def delete(expense_id):
    expenses = read_expenses()
    expenses = [e for e in expenses if e[0] != expense_id]
    write_expenses(expenses)
    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)



