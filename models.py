from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Link bypass - free solves tracking
    free_solves_today = db.Column(db.Integer, default=0)
    free_solves_date = db.Column(db.Date, nullable=True)
    
    # Relationships
    accounts = db.relationship('OnluyenAccount', backref='owner', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)

class OnluyenAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)
    proxy_key = db.Column(db.String(200), nullable=True) # Proxy key for rotation
    api_key = db.Column(db.String(200), nullable=True)   # Gemini API Key
    
    # Status
    last_active = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_code = db.Column(db.String(50), unique=True, nullable=True) # PayOS order code (nullable for SePay)
    transaction_id = db.Column(db.String(100), unique=True, nullable=True) # SePay transaction ID
    amount = db.Column(db.Integer, nullable=False)
    method = db.Column(db.String(20), default='payos') # payos, sepay, manual
    status = db.Column(db.String(20), default='PENDING') # PENDING, PAID, CANCELLED, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SolverSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('onluyen_account.id'), nullable=False)
    status = db.Column(db.String(20), default='RUNNING')
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    exam_name = db.Column(db.String(200), nullable=True)
    score_achieved = db.Column(db.Float, nullable=True)
    log_content = db.Column(db.Text, default="")
    
    # For streaming logic
    port_stream = db.Column(db.Integer, nullable=True) 

class AnswerFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quiz_name = db.Column(db.String(255), index=True)
    quiz_hash = db.Column(db.String(64), unique=True, index=True)
    content = db.Column(db.Text, nullable=False) # JSON string
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow) 

class LinkBypass(db.Model):
    """Track link bypass tokens for free solves"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    short_url = db.Column(db.String(255), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    verified_at = db.Column(db.DateTime, nullable=True)
