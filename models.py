from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets

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
# ملف تعريف شركة التثمين
# ================================
class CompanyProfile(db.Model):
    __tablename__ = 'company_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    logo_path = db.Column(db.String(255), nullable=True)
    services = db.Column(db.Text, nullable=True)
    limit_value = db.Column(db.Float, nullable=True)
    about = db.Column(db.Text, nullable=True)
    website = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # علاقة واحد لواحد مع المستخدم (الشركة)
    user = db.relationship(
        'User',
        backref=db.backref('company_profile', uselist=False, cascade="all, delete")
    )


# ================================
# البنوك المعتمدة للشركة (Many-to-Many عبر جدول وسيط)
# ================================
class CompanyApprovedBank(db.Model):
    __tablename__ = 'company_approved_banks'

    id = db.Column(db.Integer, primary_key=True)
    company_profile_id = db.Column(db.Integer, db.ForeignKey('company_profiles.id'), nullable=False)
    bank_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # علاقات اختيارية للمساعدة في الاستعلامات
    company_profile = db.relationship('CompanyProfile', backref=db.backref('approved_banks', cascade='all, delete-orphan'))
    bank_user = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint('company_profile_id', 'bank_user_id', name='uq_company_bank'),
    )


# ================================
# أرقام التواصل الخاصة بالشركة
# ================================
class CompanyContact(db.Model):
    __tablename__ = 'company_contacts'

    id = db.Column(db.Integer, primary_key=True)
    company_profile_id = db.Column(db.Integer, db.ForeignKey('company_profiles.id'), nullable=False)
    label = db.Column(db.String(100), nullable=True)  # مثل: هاتف المكتب، واتساب، جوال
    phone = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    company_profile = db.relationship('CompanyProfile', backref=db.backref('contacts', cascade='all, delete-orphan'))

# ================================
# نموذج طلب التثمين
# ================================
class ValuationRequest(db.Model):
    __tablename__ = 'valuation_requests'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=True)
    description = db.Column(db.Text, nullable=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    bank_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    value = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), default='pending')  # pending/approved/completed/revision_requested

    # علاقات ORM (اختياري لكن مفيد)
    client = db.relationship('User', foreign_keys=[client_id], backref='client_requests')
    company = db.relationship('User', foreign_keys=[company_id], backref='company_requests')
    bank = db.relationship('User', foreign_keys=[bank_id], backref='bank_requests')

# ================================
# نموذج دعوة التسجيل
# ================================
class InviteToken(db.Model):
    __tablename__ = 'invite_tokens'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)  # company أو bank
    name = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    token = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    invited_by = db.relationship('User', foreign_keys=[invited_by_id])

    @staticmethod
    def generate(email: str, role: str, invited_by_id: int = None, name: str = None, phone: str = None, expires_in_days: int = 7):
        token_value = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
        invite = InviteToken(
            email=email,
            role=role,
            name=name,
            phone=phone,
            token=token_value,
            expires_at=expires_at,
            invited_by_id=invited_by_id,
        )
        db.session.add(invite)
        db.session.commit()
        return invite
