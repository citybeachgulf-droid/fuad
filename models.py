from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ================================
# نموذج المستخدم
# ================================
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # admin, client, company, bank
    phone = db.Column(db.String(20), nullable=True)

    # تعيين كلمة المرور مع تشفير
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # التحقق من كلمة المرور
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# ================================
# نموذج طلب التثمين
# ================================
class ValuationRequest(db.Model):
    __tablename__ = 'valuation_requests'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    bank_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    value = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), default='pending')  # pending/approved/completed/revision_requested

    # علاقات ORM (اختياري لكن مفيد)
    client = db.relationship('User', foreign_keys=[client_id], backref='client_requests')
    company = db.relationship('User', foreign_keys=[company_id], backref='company_requests')
    bank = db.relationship('User', foreign_keys=[bank_id], backref='bank_requests')
