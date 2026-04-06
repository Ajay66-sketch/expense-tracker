# ============================================================
#  app.py — SurviveTheMonth
# ============================================================

import os
import calendar
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


# ── App Setup ────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'jungle-secret-change-in-production')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'survive.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ── Models ───────────────────────────────────────────────────

class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(32), unique=True, nullable=False)
    password   = db.Column(db.String(256), nullable=False)
    budget     = db.Column(db.Float, default=30000.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expenses   = db.relationship('Expense', backref='user', lazy=True,
                                 cascade='all, delete-orphan')

    def set_password(self, raw):
        self.password = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password, raw)

    def current_month_spent(self):
        now = date.today()
        total = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.user_id == self.id,
            db.extract('month', Expense.expense_date) == now.month,
            db.extract('year',  Expense.expense_date) == now.year,
        ).scalar()
        return total or 0.0

    def survival_pct(self):
        if self.budget <= 0:
            return 0
        remaining = max(0.0, self.budget - self.current_month_spent())
        return round((remaining / self.budget) * 100)


class Expense(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name         = db.Column(db.String(120), nullable=False)
    amount       = db.Column(db.Float, nullable=False)
    category     = db.Column(db.String(64), default='General')
    expense_date = db.Column(db.Date, default=date.today)
    note         = db.Column(db.String(255), default='')


# ── Auth Helpers ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('You need to log in first. 🌿', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    if 'user_id' in session:
        return db.session.get(User, session['user_id'])
    return None


# ── Context Processor ────────────────────────────────────────

@app.context_processor
def inject_current_user():
    return dict(current_user=get_current_user())


# ── Public Routes ─────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


@app.route('/demo')
def demo():
    return render_template('demo.html')


# ── Register ──────────────────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username         = request.form.get('username', '').strip().lower()
        password         = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        # register.html sends name="monthly_budget" (optional field)
        budget_raw       = request.form.get('monthly_budget', '').strip()

        if not username or len(username) < 3:
            flash('Survivor name must be at least 3 characters. 🌿', 'error')
            return render_template('register.html')

        if User.query.filter_by(username=username).first():
            flash('That survivor name is already taken. Choose another. ⚠️', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters. 🔴', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords don't match. Try again, Survivor. 🔴", 'error')
            return render_template('register.html')

        # Budget is optional — default to 30000 if blank
        budget = 30000.0
        if budget_raw:
            try:
                budget = float(budget_raw)
                if budget < 100:
                    raise ValueError
            except (ValueError, TypeError):
                flash('Please enter a valid monthly budget (min ₹100). 🌿', 'error')
                return render_template('register.html')

        user = User(username=username, budget=budget)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session['user_id'] = user.id
        flash(f'Welcome to the jungle, {username}! Your Survival Meter is live. 🌿', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


# ── Login ─────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash(f'Welcome back, {user.username}! 🌿', 'success')
            return redirect(url_for('dashboard'))

        flash("Invalid username or password. The jungle doesn't forgive. 🔴", 'error')

    return render_template('login.html')


# ── Logout ────────────────────────────────────────────────────

@app.route('/logout')
def logout():
    session.clear()
    flash('You left the jungle. Come back soon. 🌿', 'info')
    return redirect(url_for('index'))


# ── Dashboard ─────────────────────────────────────────────────

CATEGORIES = ['Rations', 'Shelter', 'Tools', 'Medicine',
              'Expedition', 'Signal', 'Supplies', 'Other']


@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    now  = date.today()

    expenses = Expense.query.filter(
        Expense.user_id == user.id,
        db.extract('month', Expense.expense_date) == now.month,
        db.extract('year',  Expense.expense_date) == now.year,
    ).order_by(Expense.expense_date.desc()).all()

    spent         = user.current_month_spent()
    remaining     = max(0.0, user.budget - spent)
    pct_remaining = user.survival_pct()
    days_left     = calendar.monthrange(now.year, now.month)[1] - now.day

    return render_template('dashboard.html',
        expenses      = expenses,
        budget        = user.budget,
        spent         = spent,
        remaining     = remaining,
        pct_remaining = pct_remaining,
        days_left     = days_left,
        month_label   = now.strftime('%B %Y'),
        today_str     = now.strftime('%Y-%m-%d'),
        categories    = CATEGORIES,
    )


# ── Add Expense ───────────────────────────────────────────────

@app.route('/add', methods=['POST'])
@login_required
def add_expense():
    user     = get_current_user()
    name     = request.form.get('name', '').strip()
    amount   = request.form.get('amount', '').strip()
    category = request.form.get('category', 'Other')
    date_raw = request.form.get('expense_date', '')
    note     = request.form.get('note', '').strip()

    if not name:
        flash('Give your expense a name. 🌿', 'error')
        return redirect(url_for('dashboard'))

    try:
        amount = float(amount)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Enter a valid amount greater than 0. 🔴', 'error')
        return redirect(url_for('dashboard'))

    try:
        exp_date = datetime.strptime(date_raw, '%Y-%m-%d').date() if date_raw else date.today()
    except ValueError:
        exp_date = date.today()

    if category not in CATEGORIES:
        category = 'Other'

    db.session.add(Expense(
        user_id      = user.id,
        name         = name,
        amount       = amount,
        category     = category,
        expense_date = exp_date,
        note         = note,
    ))
    db.session.commit()

    flash(f'₹{amount:,.0f} logged! Meter updated. 🔥', 'success')
    return redirect(url_for('dashboard'))


# ── Delete Expense ────────────────────────────────────────────

@app.route('/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    user    = get_current_user()
    expense = Expense.query.filter_by(id=expense_id, user_id=user.id).first()

    if not expense:
        flash('Expense not found. 🌿', 'error')
        return redirect(url_for('dashboard'))

    db.session.delete(expense)
    db.session.commit()
    flash('Expense removed. Meter recovered a little. 🌿', 'success')
    return redirect(url_for('dashboard'))


# ── Settings ──────────────────────────────────────────────────

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_current_user()

    if request.method == 'POST':
        budget_raw = request.form.get('budget', '').strip()
        try:
            budget = float(budget_raw)
            if budget < 100:
                raise ValueError
            user.budget = budget
            db.session.commit()
            flash('Budget updated! Your meter has been recalibrated. 🌿', 'success')
        except (ValueError, TypeError):
            flash('Invalid budget amount. 🔴', 'error')
        return redirect(url_for('settings'))

    return render_template('settings.html', user=user)


# ── API: Meter JSON ───────────────────────────────────────────

@app.route('/api/meter')
@login_required
def api_meter():
    user  = get_current_user()
    spent = user.current_month_spent()
    return jsonify({
        'pct':       user.survival_pct(),
        'spent':     spent,
        'remaining': max(0.0, user.budget - spent),
        'budget':    user.budget,
    })


# ── DB Init & Run ─────────────────────────────────────────────

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
