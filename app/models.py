from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from app.utils.time import utc_now

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    plaid_access_token = db.Column(db.String(255))  # encrypted
    item_id = db.Column(db.String(100))  # Plaid item ID
    role = db.Column(db.String(20), default='user', nullable=False)  # 'user' or 'admin'

    # Relationships
    accounts = db.relationship('Account', backref='user', lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade="all, delete-orphan")
    bills = db.relationship('Bill', backref='user', lazy=True, cascade="all, delete-orphan")
    incomes = db.relationship('Income', backref='user', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'

    @property
    def is_admin(self):
        return self.role == 'admin'


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plaid_account_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    official_name = db.Column(db.String(150))
    type = db.Column(db.String(50), nullable=False)
    subtype = db.Column(db.String(50))
    mask = db.Column(db.String(4))
    current_balance = db.Column(db.Float)
    available_balance = db.Column(db.Float)
    iso_currency_code = db.Column(db.String(3), default='USD')
    last_synced = db.Column(db.DateTime, default=utc_now)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='account', lazy=True, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Account {self.name}>'


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('account.id'), nullable=False)
    plaid_transaction_id = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    pending = db.Column(db.Boolean, default=False)
    category = db.Column(db.String(100))
    category_id = db.Column(db.String(50))
    payment_channel = db.Column(db.String(50))
    merchant_name = db.Column(db.String(150))
    location = db.Column(db.String(255))
    notes = db.Column(db.Text)
    is_recurring = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Transaction {self.name} ${self.amount}>'


class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plaid_bill_id = db.Column(db.String(100))  # optional if matched
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    frequency = db.Column(db.String(50), default='monthly')
    category = db.Column(db.String(50))
    status = db.Column(db.String(20), default="unpaid")
    autopay = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Bill {self.name} ${self.amount}>'


class Income(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plaid_income_id = db.Column(db.String(100))
    source = db.Column(db.String(120), nullable=False)
    gross_amount = db.Column(db.Float, nullable=False)
    net_amount = db.Column(db.Float)
    frequency = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def __repr__(self):
        return f'<Income {self.source} ${self.gross_amount}>'
