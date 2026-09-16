from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, get_jwt_identity, jwt_required
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import os

app = Flask(__name__)

# ── Config ─────────────────────────────────────────────────
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'dev-secret-change-me')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)

database_url = os.environ.get('DATABASE_URL', 'sqlite:///surviveThemonth.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Comma-separated list of allowed frontend origins, e.g.
# "https://your-app.vercel.app,http://localhost:3000"
FRONTEND_ORIGINS = os.environ.get('FRONTEND_ORIGINS', 'http://localhost:3000').split(',')

db = SQLAlchemy(app)
jwt = JWTManager(app)
CORS(app, resources={r"/api/*": {"origins": FRONTEND_ORIGINS}}, supports_credentials=False)

CATEGORIES = ['Rations', 'Shelter', 'Tools', 'Medicine', 'Expedition', 'Signal', 'Supplies', 'Other']
DEFAULT_BUDGET = 30000

DEMO_EXPENSES = [
    {'id': 1, 'description': 'Base Camp Groceries', 'amount': 4200, 'category': 'Rations', 'date': '2025-07-03'},
    {'id': 2, 'description': 'Rent & Utilities', 'amount': 9500, 'category': 'Shelter', 'date': '2025-07-01'},
    {'id': 3, 'description': 'Machete & Gear', 'amount': 1800, 'category': 'Tools', 'date': '2025-07-05'},
    {'id': 4, 'description': 'Medical Kit Restock', 'amount': 650, 'category': 'Medicine', 'date': '2025-07-07'},
    {'id': 5, 'description': 'Fuel & Transit', 'amount': 2100, 'category': 'Expedition', 'date': '2025-07-08'},
]

# ── Models ─────────────────────────────────────────────────
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

    def _month_expenses(self):
        now = datetime.now(timezone.utc)
        return Expense.query.filter(
            Expense.user_id == self.id,
            db.extract('month', Expense.date) == now.month,
            db.extract('year', Expense.date) == now.year
        ).all()

    def current_month_spent(self):
        return sum(e.amount for e in self._month_expenses())

    def survival_pct(self):
        if self.monthly_budget <= 0:
            return 0
        spent_pct = (self.current_month_spent() / self.monthly_budget) * 100
        return round(max(0, 100 - spent_pct), 1)

    def to_dict(self):
        return {'id': self.id, 'username': self.username, 'monthly_budget': self.monthly_budget}


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='Other')
    date = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'amount': self.amount,
            'category': self.category,
            'date': self.date.isoformat() if self.date else None,
        }


def current_user():
    return db.session.get(User, int(get_jwt_identity()))


# ── Auth ───────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    budget_raw = data.get('monthly_budget')

    if not username or not password:
        return jsonify({'error': 'Username and password are required.'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken.'}), 409

    budget = DEFAULT_BUDGET
    if budget_raw not in (None, ''):
        try:
            budget = float(budget_raw)
            if budget <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid budget amount.'}), 400

    user = User(username=username, monthly_budget=budget)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({'token': token, 'user': user.to_dict()}), 201


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials.'}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({'token': token, 'user': user.to_dict()})


@app.route('/api/me', methods=['GET'])
@jwt_required()
def me():
    user = current_user()
    return jsonify(user.to_dict())


# ── Demo (public) ──────────────────────────────────────────
@app.route('/api/demo', methods=['GET'])
def demo():
    total_spent = sum(e['amount'] for e in DEMO_EXPENSES)
    budget = DEFAULT_BUDGET
    survival_pct = max(0, round(100 - (total_spent / budget * 100), 1))
    return jsonify({
        'expenses': DEMO_EXPENSES,
        'total_spent': total_spent,
        'budget': budget,
        'survival_pct': survival_pct,
        'categories': CATEGORIES,
    })


@app.route('/api/categories', methods=['GET'])
def categories():
    return jsonify({'categories': CATEGORIES})


# ── Expenses (protected) ───────────────────────────────────
@app.route('/api/expenses', methods=['GET'])
@jwt_required()
def list_expenses():
    user = current_user()
    expenses = sorted(user._month_expenses(), key=lambda e: e.date, reverse=True)
    return jsonify({
        'expenses': [e.to_dict() for e in expenses],
        'total_spent': user.current_month_spent(),
        'survival_pct': user.survival_pct(),
        'budget': user.monthly_budget,
        'categories': CATEGORIES,
    })


@app.route('/api/expenses', methods=['POST'])
@jwt_required()
def add_expense():
    data = request.get_json(silent=True) or {}
    description = (data.get('description') or '').strip()
    amount_raw = data.get('amount')
    category = data.get('category', 'Other')

    if not description or amount_raw in (None, ''):
        return jsonify({'error': 'Description and amount are required.'}), 400
    try:
        amount = float(amount_raw)
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid amount.'}), 400

    if category not in CATEGORIES:
        category = 'Other'

    expense = Expense(description=description, amount=amount, category=category,
                       user_id=int(get_jwt_identity()))
    db.session.add(expense)
    db.session.commit()
    return jsonify(expense.to_dict()), 201


@app.route('/api/expenses/<int:expense_id>', methods=['DELETE'])
@jwt_required()
def delete_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=int(get_jwt_identity())).first()
    if not expense:
        return jsonify({'error': 'Expense not found.'}), 404
    db.session.delete(expense)
    db.session.commit()
    return jsonify({'ok': True})


# ── Settings ───────────────────────────────────────────────
@app.route('/api/settings', methods=['PUT'])
@jwt_required()
def update_settings():
    data = request.get_json(silent=True) or {}
    try:
        budget = float(data.get('monthly_budget'))
        if budget <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({'error': 'Invalid budget amount.'}), 400

    user = current_user()
    user.monthly_budget = budget
    db.session.commit()
    return jsonify(user.to_dict())


# ── Meter ──────────────────────────────────────────────────
@app.route('/api/meter', methods=['GET'])
@jwt_required()
def api_meter():
    user = current_user()
    spent = user.current_month_spent()
    return jsonify({
        'survival_pct': user.survival_pct(),
        'spent': spent,
        'budget': user.monthly_budget,
        'remaining': user.monthly_budget - spent,
    })


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False, port=int(os.environ.get('PORT', 5000)))
