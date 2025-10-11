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
    # OAuth support fields (e.g., Google sign-in)
    oauth_provider = db.Column(db.String(50), nullable=True)  # e.g., 'google'
    oauth_subject = db.Column(db.String(255), nullable=True)  # provider user id (sub)
    email_verified = db.Column(db.Boolean, nullable=False, default=False)
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
    # حد الشركة المعتمد لدى هذا البنك (اختياري لكل بنك)
    limit_value = db.Column(db.Float, nullable=True)

    # علاقات اختيارية للمساعدة في الاستعلامات
    company_profile = db.relationship('CompanyProfile', backref=db.backref('approved_banks', cascade='all, delete-orphan'))
    bank_user = db.relationship('User')

    __table_args__ = (
        db.UniqueConstraint('company_profile_id', 'bank_user_id', name='uq_company_bank'),
    )


# ================================
# البنوك اليدوية الخاصة بكل شركة
# ================================
class CompanyManualBank(db.Model):
    __tablename__ = 'company_manual_banks'

    id = db.Column(db.Integer, primary_key=True)
    company_profile_id = db.Column(db.Integer, db.ForeignKey('company_profiles.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    limit_value = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    company_profile = db.relationship(
        'CompanyProfile',
        backref=db.backref('manual_banks', cascade='all, delete-orphan')
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
    # القيمة التي طلبها البنك من العميل كتقدير مبدئي/مطلوب
    requested_amount = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(50), default='pending')  # pending/approved/completed/revision_requested/rejected
    # نوع التثمين: أرض/عقار/بناء منزل
    valuation_type = db.Column(db.String(50), nullable=True)  # values: land, property, house
    # سبب الرفض إن وُجد
    rejection_reason = db.Column(db.Text, nullable=True)
    # تاريخ الرفض
    rejected_at = db.Column(db.DateTime, nullable=True)

    # علاقات ORM (اختياري لكن مفيد)
    client = db.relationship('User', foreign_keys=[client_id], backref='client_requests')
    company = db.relationship('User', foreign_keys=[company_id], backref='company_requests')
    bank = db.relationship('User', foreign_keys=[bank_id], backref='bank_requests')
    documents = db.relationship('RequestDocument', backref='valuation_request', cascade='all, delete-orphan')
    # مواعيد الزيارة المرتبطة بالطلب
    appointments = db.relationship(
        'VisitAppointment',
        backref='valuation_request',
        cascade='all, delete-orphan'
    )

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


# ================================
# رموز التحقق عبر الهاتف (OTP)
# ================================
class OTPCode(db.Model):
    __tablename__ = 'otp_codes'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(32), index=True, nullable=False)
    code = db.Column(db.String(10), nullable=False)
    purpose = db.Column(db.String(20), nullable=False, default='login')  # login/signup
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    consumed_at = db.Column(db.DateTime, nullable=True)

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def is_consumed(self) -> bool:
        return self.consumed_at is not None

# ================================
# ملف تعريف البنك
# ================================
class BankProfile(db.Model):
    __tablename__ = 'bank_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False, index=True)
    logo_path = db.Column(db.String(255), nullable=True)
    about = db.Column(db.Text, nullable=True)
    website = db.Column(db.String(255), nullable=True)
    min_tenure_months = db.Column(db.Integer, nullable=True)
    max_tenure_months = db.Column(db.Integer, nullable=True)
    min_amount = db.Column(db.Float, nullable=True)
    max_amount = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship(
        'User',
        backref=db.backref('bank_profile', uselist=False, cascade="all, delete")
    )


# ================================
# عروض التمويل الخاصة بالبنوك
# ================================
class BankOffer(db.Model):
    __tablename__ = 'bank_offers'

    id = db.Column(db.Integer, primary_key=True)
    bank_profile_id = db.Column(db.Integer, db.ForeignKey('bank_profiles.id'), nullable=False, index=True)
    product_name = db.Column(db.String(150), nullable=False)  # مثال: قرض سكني، قرض شخصي
    rate_type = db.Column(db.String(50), nullable=True)  # ثابت/متغير
    interest_rate = db.Column(db.Float, nullable=False)  # نسبة سنوية %
    apr = db.Column(db.Float, nullable=True)
    min_amount = db.Column(db.Float, nullable=True)
    max_amount = db.Column(db.Float, nullable=True)
    min_tenure_months = db.Column(db.Integer, nullable=True)
    max_tenure_months = db.Column(db.Integer, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    bank_profile = db.relationship('BankProfile', backref=db.backref('offers', cascade='all, delete-orphan'))

# ================================
# مستندات طلب التثمين
# ================================
class RequestDocument(db.Model):
    __tablename__ = 'request_documents'

    id = db.Column(db.Integer, primary_key=True)
    valuation_request_id = db.Column(db.Integer, db.ForeignKey('valuation_requests.id'), nullable=False, index=True)
    doc_type = db.Column(db.String(100), nullable=False)  # مثل: kroki, deed, completion_certificate, maps, ids, contractor_agreement
    file_path = db.Column(db.String(255), nullable=False)  # مسار داخل static/uploads
    original_filename = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ================================
# مواعيد الزيارة
# ================================
class VisitAppointment(db.Model):
    __tablename__ = 'visit_appointments'

    id = db.Column(db.Integer, primary_key=True)
    valuation_request_id = db.Column(
        db.Integer,
        db.ForeignKey('valuation_requests.id'),
        nullable=False,
        index=True,
    )
    # وقت الموعد المقترح/النهائي
    proposed_time = db.Column(db.DateTime, nullable=False)
    # من قام باقتراحه: client أو company
    proposed_by = db.Column(db.String(20), nullable=False)
    # حالة الموعد: pending/accepted/rejected/final
    status = db.Column(db.String(20), nullable=False, default='pending')
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# ================================
# نموذج الأخبار
# ================================
class News(db.Model):
    __tablename__ = 'news'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=True)
    image_path = db.Column(db.String(255), nullable=True)  # مسار الصورة داخل static
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ================================
# سياسات القروض للبنك
# ================================
class BankLoanPolicy(db.Model):
    __tablename__ = 'bank_loan_policies'

    id = db.Column(db.Integer, primary_key=True)
    bank_profile_id = db.Column(db.Integer, db.ForeignKey('bank_profiles.id'), nullable=False, index=True)
    loan_type = db.Column(db.String(100), nullable=False)  # مثال: housing, personal, auto
    max_ratio = db.Column(db.Float, nullable=False)  # مثل 0.3 أو 0.4
    default_annual_rate = db.Column(db.Float, nullable=True)  # % سنوي
    default_years = db.Column(db.Integer, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    bank_profile = db.relationship('BankProfile', backref=db.backref('loan_policies', cascade='all, delete-orphan'))


# ================================
# تجارب العملاء (Testimonials)
# ================================
class Testimonial(db.Model):
    __tablename__ = 'testimonials'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    property_type = db.Column(db.String(50), nullable=True)  # سكني/تجاري/أرض
    rating = db.Column(db.Integer, nullable=True)  # 1..5
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


# ================================
# نظام المحادثات الداخلية (Client <-> Company)
# ================================
class Conversation(db.Model):
    __tablename__ = 'conversations'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    company_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='open')  # open/pending/closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    client = db.relationship('User', foreign_keys=[client_id], backref='client_conversations')
    company = db.relationship('User', foreign_keys=[company_id], backref='company_conversations')

    messages = db.relationship(
        'Message',
        backref='conversation',
        cascade='all, delete-orphan',
        order_by='Message.timestamp.asc()'
    )

    __table_args__ = (
        db.UniqueConstraint('client_id', 'company_id', name='uq_conversation_client_company'),
    )


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    sender = db.relationship('User')

    __table_args__ = (
        db.Index('ix_messages_conv_time', 'conversation_id', 'timestamp'),
    )


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # message_sent, status_changed, conversation_created
    meta = db.Column(db.Text, nullable=True)  # JSON string or free-form text
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    conversation = db.relationship('Conversation', backref=db.backref('activity_logs', cascade='all, delete-orphan'))
    actor = db.relationship('User')


# ================================
# الإعلانات (Advertisements)
# ================================
class Advertisement(db.Model):
    __tablename__ = 'advertisements'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=True)
    image_path = db.Column(db.String(255), nullable=False)  # مسار الصورة داخل static
    target_url = db.Column(db.String(500), nullable=True)
    placement = db.Column(db.String(50), nullable=False, default='homepage_top')  # موقع الظهور
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    start_at = db.Column(db.DateTime, nullable=True)
    end_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # يحدد إن كانت تواريخ البداية/النهاية مخزنة بتوقيت UTC (naive)
    stored_in_utc = db.Column(db.Boolean, nullable=False, default=False)

    def is_currently_visible(self) -> bool:
        """تحقق من صلاحية العرض حسب تاريخي البداية والنهاية وحالة التفعيل.

        نعتمد مقارنة بتوقيت UTC. إذا كانت الحقول مخزنة بتوقيت محلي قديم
        (قبل اعتماد التخزين على UTC)، نقوم بتحويلها إلى UTC بناءً على الإعداد.
        """
        now_utc = datetime.utcnow()

        def normalize(dt):
            if dt is None:
                return None
            if getattr(self, 'stored_in_utc', False):
                return dt
            try:
                # اعتبر القيمة المخزنة محلية ثم حوّلها إلى UTC
                from zoneinfo import ZoneInfo
                from flask import current_app
                tz_name = (current_app.config.get('TIMEZONE') if current_app else None) or 'Asia/Muscat'
                local_dt = dt.replace(tzinfo=ZoneInfo(tz_name))
                return local_dt.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
            except Exception:
                # في حال عدم توفر المنطقة الزمنية لأي سبب، نستخدم القيمة كما هي
                return dt

        start_dt = normalize(self.start_at)
        end_dt = normalize(self.end_at)

        if not self.is_active:
            return False
        if start_dt and now_utc < start_dt:
            return False
        if end_dt and now_utc > end_dt:
            return False
        return True
