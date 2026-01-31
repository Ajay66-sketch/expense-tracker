from flask import Flask, request, render_template, redirect, url_for
import os

app = Flask(_name_)

# In-memory storage for demo purposes
# You can replace this with a database later
expenses = []

# Home page: list all expenses
@app.route("/")
def home():
    return render_template("index.html", expenses=expenses)

# Add a new expense
@app.route("/add", methods=["POST"])
def add_expense():
    name = request.form.get("name")
    amount = request.form.get("amount")
    if name and amount:
        try:
            amount = float(amount)
            expenses.append({"name": name, "amount": amount})
        except ValueError:
            pass  # ignore invalid amounts
    return redirect(url_for("home"))

# Delete an expense by index
@app.route("/delete/<int:index>")
def delete_expense(index):
    if 0 <= index < len(expenses):
        expenses.pop(index)
    return redirect(url_for("home"))

if _name_ == "_main_":
    # Use Render's PORT environment variable, default to 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
