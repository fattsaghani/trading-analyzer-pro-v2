from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    
    # Admin & Subscription
    is_admin = db.Column(db.Boolean, default=False)
    is_subscribed = db.Column(db.Boolean, default=False)
    subscription_end = db.Column(db.DateTime, nullable=True)
    
    # User's uploaded trade history file
    history_file = db.Column(db.String(256), nullable=True)
    history_uploaded_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    trades = db.relationship('Trade', backref='trader', lazy='dynamic')
    accounts = db.relationship('TradeAccount', backref='owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_subscription_active(self):
        """Check if user has active subscription or is admin"""
        if self.is_admin:
            return True
        if not self.is_subscribed:
            return False
        if self.subscription_end is None:
            return False
        return datetime.utcnow() < self.subscription_end

    def __repr__(self):
        return f'<User {self.username}>'

class TradeAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    balance = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    trades = db.relationship('Trade', backref='account', lazy='dynamic')

    def __repr__(self):
        return f'<Account {self.name}>'

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10))
    volume = db.Column(db.Float)
    price = db.Column(db.Float)
    profit = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    account_id = db.Column(db.Integer, db.ForeignKey('trade_account.id'))

    def __repr__(self):
        return f'<Trade {self.symbol} {self.volume}@{self.price}>'

@login.user_loader
def load_user(id):
    return User.query.get(int(id))