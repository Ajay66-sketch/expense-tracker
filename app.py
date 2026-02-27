"""
Refactored and Optimized Expense Tracker Flask App
Requires: Flask, Flask-SQLAlchemy, Flask-WTF, Flask-Migrate
"""
import os
import csv
from io import StringIO
from decimal import Decimal, InvalidOperation
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, Response, abort, session, flash, stream_with_context
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate

# -----------------------------
# App Setup & Configuration
# -----------------------------
app = Flask(__name__)
# In production, ALWAYS pull the secret key from a secure environment variable
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key_change_in_production")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "expenses.db")

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize Extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

# -----------------------------
# Models
# -----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    
    # Store User Level (beginner, intermediate, advanced)
    level = db.Column(db.String(20), default='beginner', nullable=False)

    expenses = db.relationship('Expense', backref='user', lazy=True, cascade="all, delete-orphan")

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# -----------------------------
# Error Handlers
# -----------------------------
@app.errorhandler(500)
def internal_server_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

# -----------------------------
# Helpers
# -----------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def validate_expense_form(form):
    title = form.get('title', '').strip()
    category = form.get('category', '').strip()
    amount_raw = form.get('amount', '').strip()

    if not title or not category or not amount_raw:
        raise ValueError("All fields are required.")
    if len(title) > 100:
        raise ValueError("Title must be under 100 characters.")
    if len(category) > 50:
        raise ValueError("Category must be under 50 characters.")
    
    try:
        amount = Decimal(amount_raw)
    except InvalidOperation:
        raise ValueError("Invalid amount format.")
    
    if amount < 0 or amount > Decimal("99999999.99"):
        raise ValueError("Amount must be between 0.00 and 99,999,999.99.")

    return title, amount.quantize(Decimal("0.01")), category

# -----------------------------
# Auth Routes
# -----------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        level = request.form.get('level', 'beginner')

        if not username or not password:
            flash("All fields required", "error")
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash("Username already exists", "error")
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_pw, level=level)
        
        try:
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except Exception:
            db.session.rollback()
            flash("An error occurred during registration.", "error")

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session.permanent = True  
            return redirect(url_for('index'))
        else:
            flash("Invalid credentials", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

# -----------------------------
# Expense Routes
# -----------------------------
@app.route('/', methods=['GET', 'POST'])
@login_required
def index():
    user_id = session['user_id']
    # Updated to db.session.get to fix LegacyAPIWarning
    current_user = db.session.get(User, user_id)

    if request.method == 'POST':
        try:
            title, amount, category = validate_expense_form(request.form)
            new_expense = Expense(
                title=title,
                amount=amount,
                category=category,
                user_id=user_id
            )
            db.session.add(new_expense)
            db.session.commit()
            flash("Expense added successfully.", "success")
        except ValueError as e:
            flash(str(e), "error")
        except Exception:
            db.session.rollback()
            flash("An unexpected error occurred.", "error")
        return redirect(url_for('index'))

    # SQL Aggregations
    total = db.session.query(func.sum(Expense.amount)).filter_by(user_id=user_id).scalar() or Decimal('0.00')

    category_summary_query = db.session.query(
        Expense.category, 
        func.sum(Expense.amount).label('total')
    ).filter_by(user_id=user_id).group_by(Expense.category).all()

    category_summary = [
        {'category': row.category, 'total': float(row.total)} 
        for row in category_summary_query
    ]

    expenses = Expense.query.filter_by(user_id=user_id).order_by(Expense.id.desc()).limit(50).all()

    return render_template(
        'index.html',
        expenses=expenses,
        total=float(total),
        category_summary=category_summary,
        current_user=current_user
    )

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id != session['user_id']:
        abort(403)

    if request.method == 'POST':
        try:
            title, amount, category = validate_expense_form(request.form)
            expense.title = title
            expense.amount = amount
            expense.category = category
            db.session.commit()
            flash("Expense updated successfully.", "success")
            return redirect(url_for('index'))
        except ValueError as e:
            flash(str(e), "error")
        except Exception:
            db.session.rollback()
            flash("An unexpected error occurred.", "error")

    return render_template('edit.html', expense=expense)

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    expense = Expense.query.get_or_404(id)
    if expense.user_id != session['user_id']:
        abort(403)

    try:
        db.session.delete(expense)
        db.session.commit()
        flash("Expense deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Failed to delete expense.", "error")
    
    return redirect(url_for('index'))

@app.route('/export')
@login_required
def export():
    # Updated to db.session.get
    user = db.session.get(User, session['user_id'])
    
    # Security check - Only Advanced users can export
    if user.level != 'advanced':
        flash("Export is an Advanced feature.", "error")
        return redirect(url_for('index'))

    def generate_csv():
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(['Title', 'Amount', 'Category'])
        yield data.getvalue()
        data.seek(0)
        data.truncate(0)

        for e in Expense.query.filter_by(user_id=user.id).yield_per(100):
            writer.writerow([e.title, str(e.amount), e.category])
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    return Response(
        stream_with_context(generate_csv()),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"}
    )

# -----------------------------
# Profile / Settings Route
# -----------------------------
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # Updated to db.session.get
    user = db.session.get(User, session['user_id'])

    if request.method == 'POST':
        new_username = request.form.get('username').strip()
        new_level = request.form.get('level')

        if not new_username:
            flash("Username cannot be empty.", "error")
        else:
            # Check if username is taken by someone else
            existing = User.query.filter_by(username=new_username).first()
            if existing and existing.id != user.id:
                flash("Username already exists.", "error")
            else:
                user.username = new_username
                user.level = new_level
                try:
                    db.session.commit()
                    flash("Profile updated successfully!", "success")
                except Exception:
                    db.session.rollback()
                    flash("Error updating profile.", "error")

    return render_template('profile.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)
