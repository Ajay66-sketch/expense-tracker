import os
import resend
import threading
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime
import math

# --- 1. APP & DATABASE INITIALIZATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback_key_change_this')

database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///survival.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- 2. LOGIN MANAGER SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 3. DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    tier = db.Column(db.String(20), default='free')
    cycles = db.relationship('Cycle', backref='user', lazy=True)

class Cycle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    pocket_money = db.Column(db.Float, nullable=False)
    fixed_expenses = db.Column(db.Float, nullable=False)
    expenses = db.relationship('Expense', backref='cycle', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cycle_id = db.Column(db.Integer, db.ForeignKey('cycle.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=date.today)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    category = db.Column(db.String(50), default="General")

class PremiumInterest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    email = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

# --- 4. EMAIL NOTIFICATION ---
def send_founder_notification(signup_email, username, total):
    try:
        api_key = os.environ.get('RESEND_API_KEY')
        founder_email = os.environ.get('FOUNDER_EMAIL', 'alanjoekattakayam@gmail.com')

        if not api_key:
            print("[MAIL] No RESEND_API_KEY set, skipping notification.")
            return

        resend.api_key = api_key

        body = f"""
🎯 New Premium Waitlist Signup!

Username: {username}
Email: {signup_email or 'not provided'}
Total signups so far: {total}
Time: {datetime.utcnow().strftime('%d %b %Y, %I:%M %p')} UTC

Keep building! 🚀
— SurviveTheMonth Bot
        """.strip()

        resend.Emails.send({
            "from": "SurviveTheMonth <onboarding@resend.dev>",
            "to": founder_email,
            "subject": f"🔥 New waitlist signup #{total} — SurviveTheMonth",
            "text": body
        })

        print(f"[MAIL] Notification sent to {founder_email}")
    except Exception as e:
        print(f"[MAIL] Failed to send notification: {e}")

# --- 5. THE SURVIVAL ENGINE LOGIC ---
def get_survival_metrics(cycle, user):
    today = date.today()
    if not cycle: return None

    total_days = max(1, (cycle.end_date - cycle.start_date).days + 1)
    days_passed = max(1, (today - cycle.start_date).days)
    remaining_days = max(1, total_days - days_passed)

    disposable_income = cycle.pocket_money - cycle.fixed_expenses
    total_spent = sum(e.amount for e in cycle.expenses)
    spent_today = sum(e.amount for e in cycle.expenses if e.date == today)
    remaining_money = disposable_income - total_spent

    safe_daily_limit = remaining_money / remaining_days if remaining_money > 0 else 0

    if remaining_money <= 0:
        feedback = {"type": "danger", "msg": "🚨 Broke Mode! You are officially out of safe money."}
    elif spent_today > safe_daily_limit:
        feedback = {"type": "warning", "msg": "⚠️ You overspent today. Tomorrow's limit will drop."}
    elif spent_today == 0:
        feedback = {"type": "success", "msg": "🧘 Zero spent today! Your limit for tomorrow is growing."}
    else:
        feedback = {"type": "info", "msg": "🎯 Excellent control. You are within your survival limit."}

    return {
        "remaining_money": remaining_money,
        "remaining_days": remaining_days,
        "safe_daily_limit": round(safe_daily_limit, 2),
        "spent_today": spent_today,
        "feedback": feedback
    }

# --- 6. ROUTES (AUTH) ---

# NEW: Marketing landing page at root for guests
@app.route('/home')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_exists = User.query.filter_by(username=username).first()
        if user_exists:
            flash('Username already exists. Please login.', 'danger')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        session['show_welcome'] = True   # trigger welcome banner
        return redirect(url_for('edit'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            session['show_welcome'] = True   # trigger welcome banner
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))   # send to landing page after logout

# --- 7. ROUTES (CORE APP) ---

# Root now requires login and shows the dashboard
@app.route('/')
@login_required
def index():
    active_cycle = Cycle.query.filter_by(user_id=current_user.id).order_by(Cycle.id.desc()).first()
    if not active_cycle:
        return redirect(url_for('edit'))

    metrics = get_survival_metrics(active_cycle, current_user)
    expenses = Expense.query.filter_by(cycle_id=active_cycle.id).order_by(Expense.timestamp.desc()).all()
    premium_count = PremiumInterest.query.count()

    # Pop welcome flag so the banner only shows once
    show_welcome = session.pop('show_welcome', False)

    return render_template(
        'index.html',
        metrics=metrics,
        cycle=active_cycle,
        expenses=expenses,
        premium_count=premium_count,
        show_welcome=show_welcome
    )

@app.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    if request.method == 'POST':
        try:
            pocket_money = float(request.form.get('pocket_money'))
            fixed_expenses = float(request.form.get('fixed_expenses'))
            start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()
            new_cycle = Cycle(
                user_id=current_user.id,
                pocket_money=pocket_money,
                fixed_expenses=fixed_expenses,
                start_date=start_date,
                end_date=end_date
            )
            db.session.add(new_cycle)
            db.session.commit()
            flash('Month setup complete! Survive well.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash('Error setting up month. Please check your inputs.', 'danger')
            return redirect(url_for('edit'))
    active_cycle = Cycle.query.filter_by(user_id=current_user.id).order_by(Cycle.id.desc()).first()
    return render_template('edit.html', has_cycle=active_cycle is not None)

@app.route('/log_expense', methods=['POST'])
@login_required
def log_expense():
    amount = float(request.form.get('amount'))
    active_cycle = Cycle.query.filter_by(user_id=current_user.id).order_by(Cycle.id.desc()).first()
    if active_cycle:
        new_expense = Expense(amount=amount, cycle_id=active_cycle.id, date=date.today())
        db.session.add(new_expense)
        db.session.commit()
        flash("Expense logged!", "success")
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    active_cycle = Cycle.query.filter_by(user_id=current_user.id).order_by(Cycle.id.desc()).first()
    total_expenses = 0
    expense_count = 0
    if active_cycle:
        total_expenses = sum(e.amount for e in active_cycle.expenses)
        expense_count = len(active_cycle.expenses)
    return render_template('profile.html', total_expenses=total_expenses, expense_count=expense_count, cycle=active_cycle)

# --- 8. PREMIUM INTEREST ROUTE ---
@app.route('/premium_interest', methods=['POST'])
@login_required
def premium_interest():
    data = request.get_json()
    email = data.get('email', '').strip() if data else ''
    interest = PremiumInterest(user_id=current_user.id, email=email or None)
    db.session.add(interest)
    db.session.commit()
    total = PremiumInterest.query.count()
    print(f"[PREMIUM] Waitlist signup — email: {email or 'not provided'} | Total: {total}")
    threading.Thread(target=send_founder_notification, args=(email, current_user.username, total), daemon=True).start()
    return jsonify({"status": "ok", "total": total})

# --- 9. AUTO-CREATE TABLES ---
with app.app_context():
    if os.environ.get('RESET_DB') == 'true':
        db.drop_all()
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
