from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    accounts = db.relationship('TradeAccount', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class TradeAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_number = db.Column(db.String(50))
    broker_name = db.Column(db.String(100))
    account_name = db.Column(db.String(100))
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    trades = db.relationship('Trade', backref='account', lazy=True)

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('trade_account.id'), nullable=False)
    ticket = db.Column(db.String(50))
    symbol = db.Column(db.String(20))
    type = db.Column(db.String(10))  # buy/sell
    size = db.Float()
    open_price = db.Float()
    close_price = db.Float()
    profit = db.Float()
    open_time = db.Column(db.DateTime)
    close_time = db.Column(db.DateTime)
    commission = db.Float()
    swap = db.Float()