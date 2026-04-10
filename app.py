from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from functools import wraps
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'jungle-survival-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///surviveThemonth.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ── Favicon ────────────────────────────────────────────────
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

CATEGORIES = ['Rations', 'Shelter', 'Tools', 'Medicine', 'Expedition', 'Signal', 'Supplies', 'Other']
DEFAULT_BUDGET = 30000

DEMO_EXPENSES = [
    {'id': 1, 'description': 'Base Camp Groceries', 'amount': 4200, 'category': 'Rations', 'date': '2025-07-03'},
    {'id': 2, 'description': 'Rent & Utilities', 'amount': 9500, 'category': 'Shelter', 'date': '2025-07-01'},
    {'id': 3, 'description': 'Machete & Gear', 'amount': 1800, 'category': 'Tools', 'date': '2025-07-05'},
    {'id': 4, 'description': 'Medical Kit Restock', 'amount': 650, 'category': 'Medicine', 'date': '2025-07-07'},
    {'id': 5, 'description': 'Fuel & Transit', 'amount': 2100, 'category': 'Expedition', 'date': '2025-07-08'},
]

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    monthly_budget = db.Column(db.Float, default=DEFAULT_BUDGET)
    expenses = db.relationship('Expense', backref='user', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def survival_pct(self):
        now = datetime.now(timezone.utc)
        month_expenses = Expense.query.filter(
            Expense.user_id == self.id,
            db.extract('month', Expense.date) == now.month,
            db.extract('year', Expense.date) == now.year
        ).all()
        total_spent = sum(e.amount for e in month_expenses)
        if self.monthly_budget <= 0:
            return 0
        spent_pct = (total_spent / self.monthly_budget) * 100
        survival = max(0, 100 - spent_pct)
        return round(survival, 1)

    def current_month_spent(self):
        now = datetime.now(timezone.utc)
        month_expenses = Expense.query.filter(
            Expense.user_id == self.id,
            db.extract('month', Expense.date) == now.month,
            db.extract('year', Expense.date) == now.year
        ).all()
        return sum(e.amount for e in month_expenses)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='Other')
    date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('You need to log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            flash(f'Welcome back, {user.username}! The jungle awaits.', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials. Try again, survivor.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        budget_str = request.form.get('monthly_budget', '').strip()

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('register.html')
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Username already taken. Choose another.', 'danger')
            return render_template('register.html')

        budget = DEFAULT_BUDGET
        if budget_str:
            try:
                budget = float(budget_str)
                if budget <= 0:
                    raise ValueError
            except ValueError:
                flash('Invalid budget amount.', 'danger')
                return render_template('register.html')

        user = User(username=username, monthly_budget=budget)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        flash(f'Welcome to the jungle, {username}! Survive the month.', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/demo')
def demo():
    total_spent = sum(e['amount'] for e in DEMO_EXPENSES)
    budget = DEFAULT_BUDGET
    survival_pct = max(0, round(100 - (total_spent / budget * 100), 1))
    return render_template('demo.html',
                           expenses=DEMO_EXPENSES,
                           total_spent=total_spent,
                           budget=budget,
                           survival_pct=survival_pct,
                           categories=CATEGORIES)

@app.route('/dashboard')
@login_required
def dashboard():
    user = db.session.get(User, session['user_id'])
    now = datetime.now(timezone.utc)
    expenses = Expense.query.filter(
        Expense.user_id == user.id,
        db.extract('month', Expense.date) == now.month,
        db.extract('year', Expense.date) == now.year
    ).order_by(Expense.date.desc()).all()
    total_spent = sum(e.amount for e in expenses)
    survival_pct = user.survival_pct()
    return render_template('dashboard.html',
                           user=user,
                           expenses=expenses,
                           total_spent=total_spent,
                           survival_pct=survival_pct,
                           categories=CATEGORIES,
                           now=now)

@app.route('/add', methods=['POST'])
@login_required
def add_expense():
    description = request.form.get('description', '').strip()
    amount_str = request.form.get('amount', '').strip()
    category = request.form.get('category', 'Other')

    if not description or not amount_str:
        flash('Description and amount are required.', 'danger')
        return redirect(url_for('dashboard'))
    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash('Invalid amount entered.', 'danger')
        return redirect(url_for('dashboard'))

    if category not in CATEGORIES:
        category = 'Other'

    expense = Expense(
        description=description,
        amount=amount,
        category=category,
        user_id=session['user_id']
    )
    db.session.add(expense)
    db.session.commit()
    flash(f'Expense logged: {description} (₹{amount:,.0f})', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=session['user_id']).first()
    if not expense:
        flash('Expense not found.', 'danger')
        return redirect(url_for('dashboard'))
    db.session.delete(expense)
    db.session.commit()
    flash('Expense removed from the log.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user = db.session.get(User, session['user_id'])
    if request.method == 'POST':
        budget_str = request.form.get('monthly_budget', '').strip()
        try:
            budget = float(budget_str)
            if budget <= 0:
                raise ValueError
            user.monthly_budget = budget
            db.session.commit()
            flash('Budget updated. Survive harder.', 'success')
        except ValueError:
            flash('Invalid budget amount.', 'danger')
        return redirect(url_for('settings'))
    return render_template('settings.html', user=user)

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    flash('You have left the jungle. See you next month.', 'info')
    return redirect(url_for('login'))

@app.route('/api/meter')
@login_required
def api_meter():
    user = db.session.get(User, session['user_id'])
    pct = user.survival_pct()
    spent = user.current_month_spent()
    return jsonify({
        'survival_pct': pct,
        'spent': spent,
        'budget': user.monthly_budget,
        'remaining': user.monthly_budget - spent
    })

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
