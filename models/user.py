from extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import random


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(100), nullable=False)
    email        = db.Column(db.String(150), unique=True, nullable=False)
    password_hash= db.Column(db.String(256), nullable=False)
    phone        = db.Column(db.String(15), nullable=True)
    ward         = db.Column(db.String(100), nullable=True)
    role         = db.Column(db.String(20), default='citizen')  # citizen | official | admin
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Email OTP verification ────────────────────────────────────────────────
    email_verified  = db.Column(db.Boolean, default=False)
    otp_code        = db.Column(db.String(6), nullable=True)
    otp_expires_at  = db.Column(db.DateTime, nullable=True)

    # Relationships
    complaints = db.relationship('Complaint', backref='reporter', lazy=True,
                                 foreign_keys='Complaint.user_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_otp(self):
        """Generate a 6-digit OTP valid for 10 minutes."""
        from datetime import timedelta
        self.otp_code = str(random.randint(100000, 999999))
        self.otp_expires_at = datetime.utcnow() + timedelta(minutes=10)
        return self.otp_code

    def verify_otp(self, code):
        if not self.otp_code or not self.otp_expires_at:
            return False
        if datetime.utcnow() > self.otp_expires_at:
            return False
        if self.otp_code != str(code).strip():
            return False
        # Clear OTP after success
        self.otp_code = None
        self.otp_expires_at = None
        self.email_verified = True
        return True

    def __repr__(self):
        return f'<User {self.email} [{self.role}]>'
