# ============================================================
#  SurviveTheMonth — app.py  (complete, copy-paste ready)
# ============================================================

import os
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template, redirect, url_for,
    flash, request, session, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# ── App setup ────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'jungle-survive-dev-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', 'sqlite:///survive.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# ── Models ───────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'
    id             = db.Column(db.Integer, primary_key=True)
    username       = db.Column(db.String(80), unique=True, nullable=False)
    email          = db.Column(db.String(120), unique=True, nullable=True)
    password_hash  = db.Column(db.String(256), nullable=False)
    monthly_budget = db.Column(db.Float, default=30000.0)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    expenses       = db.relationship('Expense', backref='user', lazy=True,
                                     cascade='all, delete-orphan')

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class Expense(db.Model):
    __tablename__ = 'expenses'
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name         = db.Column(db.String(120), nullable=False)
    amount       = db.Column(db.Float, nullable=False)
    category     = db.Column(db.String(60), default='Other')
    note         = db.Column(db.String(255), nullable=True)
    expense_date = db.Column(db.Date, default=date.today)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


# ── Helpers ──────────────────────────────────────────────────
def get_current_user():
    if 'user_id' not in session:
        return None
    return db.session.get(User, session['user_id'])


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access your dashboard.', 'info')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def month_summary(user):
    today     = date.today()
    first_day = today.replace(day=1)
    if today.month == 12:
        last_day = date(today.year, 12, 31)
    else:
        last_day = date(today.year, today.month + 1, 1) - timedelta(days=1)

    expenses = Expense.query.filter(
        Expense.user_id      == user.id,
        Expense.expense_date >= first_day,
        Expense.expense_date <= today
    ).order_by(Expense.expense_date.desc(), Expense.created_at.desc()).all()

    spent         = sum(e.amount for e in expenses)
    budget        = user.monthly_budget
    remaining     = max(0.0, budget - spent)
    pct_remaining = round((remaining / budget) * 100) if budget > 0 else 0
    days_left     = (last_day - today).days + 1

    return dict(
        budget        = budget,
        spent         = spent,
        remaining     = remaining,
        pct_remaining = pct_remaining,
        days_left     = days_left,
        expenses      = expenses,
        month_label   = today.strftime('%B %Y'),
    )


# ── Context processor — injects current_user into ALL templates
@app.context_processor
def inject_current_user():
    return {'current_user': get_current_user()}


# ── Public routes ────────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/demo')
def demo():
    return render_template('demo.html')


# ── Auth routes ──────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username:
            flash('Username is required.', 'error')
            return render_template('login.html')
        if not password:
            flash('Password is required.', 'error')
            return render_template('login.html')

        user = User.query.filter(
            db.func.lower(User.username) == username.lower()
        ).first()

        if user and user.check_password(password):
            session.clear()
            session['user_id'] = user.id
            flash(f'Welcome back, {user.username}! 🌿', 'success')
            return redirect(url_for('dashboard'))

        flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm  = request.form.get('confirm_password', '').strip()
        budget   = request.form.get('monthly_budget', '30000').strip()

        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if User.query.filter(db.func.lower(User.username) == username.lower()).first():
            errors.append('That username is already taken.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html', username=username, budget=budget)

        try:
            budget_val = float(budget)
            if budget_val <= 0:
                raise ValueError
        except (ValueError, TypeError):
            budget_val = 30000.0

        user = User(username=username, monthly_budget=budget_val)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        session.clear()
        session['user_id'] = user.id
        flash('Account created! Your jungle survival begins now. 🌿', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out. Stay safe out there. 🌿', 'info')
    return redirect(url_for('index'))


# ── App routes (login required) ──────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    user    = get_current_user()
    summary = month_summary(user)
    return render_template("dashboard.html", user=user, today_str=date.today().isoformat(), **summary)


@app.route('/add-expense', methods=['POST'])
@login_required
def add_expense():
    user     = get_current_user()
    name     = request.form.get('name', '').strip()
    amount   = request.form.get('amount', '').strip()
    category = request.form.get('category', 'Other').strip()
    note     = request.form.get('note', '').strip()
    exp_date = request.form.get('expense_date', str(date.today())).strip()

    if not name:
        flash('Expense name is required.', 'error')
        return redirect(url_for('dashboard'))
    try:
        amount_val = float(amount)
        if amount_val <= 0:
            raise ValueError
    except (ValueError, TypeError):
        flash('Enter a valid amount greater than 0.', 'error')
        return redirect(url_for('dashboard'))

    try:
        date_val = datetime.strptime(exp_date, '%Y-%m-%d').date()
    except ValueError:
        date_val = date.today()

    db.session.add(Expense(
        user_id=user.id, name=name, amount=amount_val,
        category=category, note=note or None, expense_date=date_val
    ))
    db.session.commit()
    flash(f'"{name}" logged! Meter updated. Survive on. 🔥', 'success')
    return redirect(url_for('dashboard'))


@app.route('/delete-expense/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    user    = get_current_user()
    expense = Expense.query.filter_by(id=expense_id, user_id=user.id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    flash('Expense removed.', 'info')
    return redirect(url_for('dashboard'))


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = get_current_user()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_budget':
            try:
                val = float(request.form.get('monthly_budget', 0))
                if val <= 0:
                    raise ValueError
                user.monthly_budget = val
                db.session.commit()
                flash('Budget updated! 🌿', 'success')
            except (ValueError, TypeError):
                flash('Enter a valid budget amount.', 'error')
        elif action == 'change_password':
            cur = request.form.get('current_password', '')
            new = request.form.get('new_password', '')
            con = request.form.get('confirm_password', '')
            if not user.check_password(cur):
                flash('Current password is incorrect.', 'error')
            elif len(new) < 6:
                flash('New password must be at least 6 characters.', 'error')
            elif new != con:
                flash('New passwords do not match.', 'error')
            else:
                user.set_password(new)
                db.session.commit()
                flash('Password changed successfully.', 'success')
        return redirect(url_for('settings'))
    return render_template('settings.html', user=user)


# ── JSON API ─────────────────────────────────────────────────
@app.route('/api/meter')
@login_required
def api_meter():
    summary = month_summary(get_current_user())
    return jsonify({k: summary[k] for k in
                    ('pct_remaining', 'spent', 'remaining', 'budget', 'days_left')})


# ── Error handlers ───────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# ── Init & run ───────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('[SurviveTheMonth] Database ready.')
    app.run(debug=True, host='0.0.0.0', port=5000)

