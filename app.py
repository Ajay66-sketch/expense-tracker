"""
SurviveTheMonth — app.py
Full implementation: SQLite database, real auth, registration,
expense logging, dashboard with live data.
"""

import os
import sqlite3
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, g, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")

# ── Database path ─────────────────────────────────────────────
DATABASE = os.path.join(os.path.dirname(__file__), "survive.db")

# ── Jungle expense categories ─────────────────────────────────
CATEGORIES = [
    {"id": "shelter",    "label": "Shelter",             "icon": "🏕️",  "tag": "fixed"},
    {"id": "supplies",   "label": "Base Camp Supplies",  "icon": "🥫",  "tag": "essential"},
    {"id": "transport",  "label": "Jungle Transit",      "icon": "🛻",  "tag": "essential"},
    {"id": "signals",    "label": "Signal Tower",        "icon": "📡",  "tag": "fixed"},
    {"id": "medic",      "label": "Field Medic Kit",     "icon": "🧴",  "tag": "essential"},
    {"id": "intel",      "label": "Survival Intel",      "icon": "📖",  "tag": "optional"},
    {"id": "morale",     "label": "Morale Booster",      "icon": "🎬",  "tag": "optional"},
    {"id": "luxury",     "label": "Luxury Rations",      "icon": "🍜",  "tag": "luxury"},
    {"id": "fuel",       "label": "Fuel Depot",          "icon": "⛽",  "tag": "essential"},
    {"id": "other",      "label": "Other",               "icon": "🎒",  "tag": "optional"},
]

TAG_CLASSES = {
    "fixed":     "tag--fixed",
    "essential": "tag--essential",
    "luxury":    "tag--luxury",
    "optional":  "tag--optional",
}

# ═══════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT    NOT NULL UNIQUE,
            username    TEXT    NOT NULL,
            password    TEXT    NOT NULL,
            budget      REAL    NOT NULL DEFAULT 25000,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            amount      REAL    NOT NULL,
            note        TEXT    NOT NULL DEFAULT '',
            category    TEXT    NOT NULL DEFAULT 'other',
            logged_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );
    """)
    db.commit()


with app.app_context():
    init_db()


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            flash("Log in to access your dashboard.", "info")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()


def get_month_stats(user_id, year, month):
    db = get_db()
    user = db.execute("SELECT budget FROM users WHERE id = ?", (user_id,)).fetchone()
    budget = user["budget"] if user else 25000

    rows = db.execute("""
        SELECT e.*
        FROM expenses e
        WHERE e.user_id = ?
          AND strftime('%Y', e.logged_at) = ?
          AND strftime('%m', e.logged_at) = ?
        ORDER BY e.logged_at DESC
    """, (user_id, str(year), f"{month:02d}")).fetchall()

    total_spent = sum(r["amount"] for r in rows)
    remaining   = max(0.0, budget - total_spent)
    meter_pct   = max(0, min(100, round((remaining / budget) * 100))) if budget > 0 else 0

    cat_map = {c["id"]: c for c in CATEGORIES}
    expenses = []
    for r in rows:
        cat = cat_map.get(r["category"], cat_map["other"])
        expenses.append({
            "id":        r["id"],
            "amount":    r["amount"],
            "note":      r["note"],
            "category":  r["category"],
            "label":     cat["label"],
            "icon":      cat["icon"],
            "tag":       cat["tag"],
            "tag_class": TAG_CLASSES.get(cat["tag"], "tag--optional"),
            "logged_at": r["logged_at"],
        })

    return {
        "budget":        budget,
        "total_spent":   total_spent,
        "remaining":     remaining,
        "meter_pct":     meter_pct,
        "expenses":      expenses,
        "expense_count": len(expenses),
    }


def get_streak(user_id):
    db = get_db()
    rows = db.execute("""
        SELECT DISTINCT date(logged_at) as day
        FROM expenses
        WHERE user_id = ?
        ORDER BY day DESC
    """, (user_id,)).fetchall()

    if not rows:
        return 0

    streak = 0
    check = date.today()
    for row in rows:
        day = date.fromisoformat(row["day"])
        if day == check:
            streak += 1
            check = date.fromordinal(check.toordinal() - 1)
        elif day < check:
            break
    return streak


# ═══════════════════════════════════════════════════════════════
# ROUTES — PUBLIC
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/demo")
def demo():
    return render_template("demo.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")
        budget   = request.form.get("budget", "25000").strip()

        errors = []
        if not email or "@" not in email:
            errors.append("A valid email is required.")
        if not username or len(username) < 2:
            errors.append("Username must be at least 2 characters.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")
        try:
            budget_val = float(budget)
            if budget_val <= 0:
                raise ValueError
        except ValueError:
            errors.append("Enter a valid monthly budget (e.g. 25000).")
            budget_val = 25000.0

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form=request.form, budget=budget)

        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("That email is already registered. Log in instead?", "error")
            return render_template("register.html", form=request.form, budget=budget)

        pw_hash = generate_password_hash(password)
        cur = db.execute(
            "INSERT INTO users (email, username, password, budget) VALUES (?, ?, ?, ?)",
            (email, username, pw_hash, budget_val)
        )
        db.commit()

        session["user_id"]    = cur.lastrowid
        session["user_email"] = email
        session["username"]   = username
        flash(f"Welcome to the jungle, {username}! 🌿 Your survival starts now.", "success")
        return redirect(url_for("dashboard"))

    return render_template("register.html", form={}, budget="25000")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.", "error")
            return render_template("login.html")

        db   = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session["user_id"]    = user["id"]
        session["user_email"] = user["email"]
        session["username"]   = user["username"]
        flash(f"Welcome back, {user['username']}! 🌿", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You've left the jungle. Come back soon. 🌿", "info")
    return redirect(url_for("landing"))


@app.route("/forgot-password")
def forgot_password():
    flash("Password reset coming soon.", "info")
    return redirect(url_for("login"))


# ═══════════════════════════════════════════════════════════════
# ROUTES — PROTECTED
# ═══════════════════════════════════════════════════════════════

@app.route("/dashboard")
@login_required
def dashboard():
    user   = get_current_user()
    now    = datetime.now()
    stats  = get_month_stats(user["id"], now.year, now.month)
    streak = get_streak(user["id"])

    return render_template(
        "dashboard.html",
        user       = user,
        stats      = stats,
        streak     = streak,
        categories = CATEGORIES,
        now        = now,
        tag_classes = TAG_CLASSES,
    )


@app.route("/expenses/add", methods=["POST"])
@login_required
def add_expense():
    user     = get_current_user()
    amount   = request.form.get("amount", "").strip()
    note     = request.form.get("note", "").strip()
    category = request.form.get("category", "other").strip()
    is_ajax  = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    try:
        amount_val = float(amount)
        if amount_val <= 0:
            raise ValueError
    except ValueError:
        if is_ajax:
            return jsonify({"ok": False, "error": "Enter a valid amount."}), 400
        flash("Enter a valid amount.", "error")
        return redirect(url_for("dashboard"))

    if not note:
        note = next((c["label"] for c in CATEGORIES if c["id"] == category), "Expense")

    db = get_db()
    db.execute(
        "INSERT INTO expenses (user_id, amount, note, category) VALUES (?, ?, ?, ?)",
        (user["id"], amount_val, note, category)
    )
    db.commit()

    if is_ajax:
        now    = datetime.now()
        stats  = get_month_stats(user["id"], now.year, now.month)
        streak = get_streak(user["id"])
        cat    = next((c for c in CATEGORIES if c["id"] == category), CATEGORIES[-1])
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return jsonify({
            "ok":          True,
            "meter_pct":   stats["meter_pct"],
            "total_spent": stats["total_spent"],
            "remaining":   stats["remaining"],
            "budget":      stats["budget"],
            "streak":      streak,
            "expense": {
                "id":       new_id,
                "amount":   amount_val,
                "note":     note,
                "label":    cat["label"],
                "icon":     cat["icon"],
                "tag":      cat["tag"],
                "tag_class": TAG_CLASSES.get(cat["tag"], "tag--optional"),
                "logged_at": now.strftime("%d %b, %H:%M"),
            }
        })

    flash("Expense logged! Meter updated. 🔥", "success")
    return redirect(url_for("dashboard"))


@app.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(expense_id):
    user = get_current_user()
    db   = get_db()
    db.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user["id"]))
    db.commit()

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        now   = datetime.now()
        stats = get_month_stats(user["id"], now.year, now.month)
        return jsonify({
            "ok":          True,
            "meter_pct":   stats["meter_pct"],
            "total_spent": stats["total_spent"],
            "remaining":   stats["remaining"],
        })

    flash("Expense removed.", "info")
    return redirect(url_for("dashboard"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = get_current_user()

    if request.method == "POST":
        action = request.form.get("action")
        db = get_db()

        if action == "update_budget":
            try:
                budget = float(request.form.get("budget", 0))
                if budget <= 0:
                    raise ValueError
                db.execute("UPDATE users SET budget = ? WHERE id = ?", (budget, user["id"]))
                db.commit()
                flash("Monthly budget updated! 🎯", "success")
            except ValueError:
                flash("Enter a valid budget amount.", "error")

        elif action == "update_username":
            username = request.form.get("username", "").strip()
            if len(username) >= 2:
                db.execute("UPDATE users SET username = ? WHERE id = ?", (username, user["id"]))
                db.commit()
                session["username"] = username
                flash("Username updated!", "success")
            else:
                flash("Username must be at least 2 characters.", "error")

        elif action == "change_password":
            current = request.form.get("current_password", "")
            new_pw  = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")
            if not check_password_hash(user["password"], current):
                flash("Current password is incorrect.", "error")
            elif len(new_pw) < 6:
                flash("New password must be at least 6 characters.", "error")
            elif new_pw != confirm:
                flash("Passwords do not match.", "error")
            else:
                db.execute("UPDATE users SET password = ? WHERE id = ?",
                           (generate_password_hash(new_pw), user["id"]))
                db.commit()
                flash("Password changed successfully! 🔒", "success")

        return redirect(url_for("settings"))

    return render_template("settings.html", user=user)


# ── Error handlers ────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("landing.html"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("landing.html"), 500


# ── Run ───────────────────────────────────────────────────────

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=5000)
