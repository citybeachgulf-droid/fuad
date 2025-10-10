from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, InviteToken, OTPCode
from datetime import datetime, timedelta
from authlib.integrations.flask_client import OAuth
import secrets
from utils import generate_otp_code, format_phone_e164, send_sms_via_twilio
from sqlalchemy import and_

# Blueprint مع مسار صحيح لمجلد القوالب
auth = Blueprint('auth', __name__, template_folder='../templates/auth')

# Initialize OAuth lazily using app context
_oauth = None

def get_oauth():
    global _oauth
    if _oauth is None:
        app = current_app
        oauth = OAuth(app)
        # Google
        oauth.register(
            name='google',
            client_id=app.config.get('GOOGLE_CLIENT_ID'),
            client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )
        # Apple (OpenID Connect - discovery is static; use custom endpoints)
        oauth.register(
            name='apple',
            client_id=app.config.get('APPLE_CLIENT_ID'),
            client_secret=app.config.get('APPLE_CLIENT_SECRET'),
            api_base_url='https://appleid.apple.com',
            authorize_url='https://appleid.apple.com/auth/authorize',
            access_token_url='https://appleid.apple.com/auth/token',
            client_kwargs={'scope': 'name email', 'response_mode': 'form_post', 'response_type': 'code'},
        )
        _oauth = oauth
    return _oauth

# --- صفحة تسجيل الدخول ---
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        # البحث عن المستخدم
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):  # التحقق من كلمة المرور المشفرة
            login_user(user)
            flash('تم تسجيل الدخول بنجاح', 'success')

            # إعادة التوجيه حسب الدور
            if user.role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.role == 'company':
                return redirect(url_for('company.dashboard'))
            elif user.role == 'bank':
                return redirect(url_for('bank.dashboard'))
            else:
                return redirect(url_for('main.landing'))
        else:
            flash('البريد الإلكتروني أو كلمة المرور خاطئة', 'danger')

    return render_template('login.html')


# --- تسجيل الدخول/إنشاء حساب عبر الهاتف (طلب رمز) ---
@auth.route('/phone', methods=['GET', 'POST'])
def phone_entry():
    if request.method == 'POST':
        raw_phone = (request.form.get('phone') or '').strip()
        phone = format_phone_e164(raw_phone)
        if not phone:
            flash('يرجى إدخال رقم هاتف صالح', 'danger')
            return render_template('phone.html')

        # لا ترسل رمز تحقق للحسابات الجديدة برقم هاتف جديد
        existing_user = User.query.filter_by(phone=phone).first()
        if not existing_user:
            flash('إنشاء حساب جديد برقم الهاتف غير متاح حاليًا. الرجاء التسجيل بالبريد الإلكتروني.', 'warning')
            return redirect(url_for('auth.signup'))

        purpose = (request.form.get('purpose') or 'login').strip()
        # توليد رمز OTP وتخزينه
        code = generate_otp_code(6)
        ttl_seconds = int(current_app.config.get('OTP_TTL_SECONDS', 300))
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        otp = OTPCode(phone=phone, code=code, purpose=purpose, expires_at=expires_at)
        db.session.add(otp)
        db.session.commit()

        message = f"رمز الدخول: {code}. صالح لمدة 5 دقائق"
        sent = send_sms_via_twilio(phone, message)
        if sent:
            flash('تم إرسال رمز التحقق عبر الرسائل القصيرة', 'info')
        else:
            flash('تعذر إرسال الرسالة القصيرة. الرجاء إدخال الرمز يدويًا في بيئة التطوير: ' + code, 'warning')

        return redirect(url_for('auth.verify_otp', phone=phone, purpose=purpose))

    return render_template('phone.html')


# --- التحقق من رمز OTP ---
@auth.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    phone = request.args.get('phone') if request.method == 'GET' else request.form.get('phone')
    purpose = request.args.get('purpose') if request.method == 'GET' else request.form.get('purpose')
    if request.method == 'POST':
        code = (request.form.get('code') or '').strip()
        normalized_phone = format_phone_e164(phone)
        if not (code and normalized_phone):
            flash('يرجى إدخال الرمز ورقم الهاتف', 'danger')
            return render_template('verify_otp.html', phone=phone, purpose=purpose)

        # احصل على أحدث رمز غير مستخدم لهذا الهاتف والغرض
        otp = OTPCode.query.filter(
            and_(
                OTPCode.phone == normalized_phone,
                OTPCode.purpose == purpose,
                OTPCode.consumed_at.is_(None)
            )
        ).order_by(OTPCode.id.desc()).first()

        if not otp:
            flash('لم يتم العثور على رمز صالح. الرجاء إعادة الإرسال.', 'danger')
            return redirect(url_for('auth.phone_entry'))
        if otp.is_expired():
            flash('انتهت صلاحية الرمز. الرجاء إعادة الإرسال.', 'danger')
            return redirect(url_for('auth.phone_entry'))

        otp.attempts += 1
        if otp.code != code:
            db.session.commit()
            flash('رمز غير صحيح', 'danger')
            return render_template('verify_otp.html', phone=normalized_phone, purpose=purpose)

        # الرمز صحيح: اعتبره مستهلكًا
        otp.consumed_at = datetime.utcnow()
        db.session.commit()

        # أنشئ/اجلب المستخدم بناءً على الهاتف
        user = User.query.filter_by(phone=normalized_phone).first()
        if not user:
            # إنشاء حساب عميل افتراضي باستخدام هاتف فقط
            # ضع بريدًا اصطناعيًا فريدًا لتلبية القيد الحالي
            pseudo_email = f"phone-{normalized_phone.replace('+','') }@users.local"
            if User.query.filter_by(email=pseudo_email).first():
                pseudo_email = f"phone-{normalized_phone.replace('+','')}-{otp.id}@users.local"
            user = User(name=normalized_phone, email=pseudo_email, role='client', phone=normalized_phone)
            # كلمة مرور عشوائية
            user.set_password(secrets.token_urlsafe(16))
            db.session.add(user)
            db.session.commit()

        login_user(user)
        flash('تم تسجيل الدخول برقم الهاتف', 'success')
        return redirect(url_for('client.dashboard'))

    # GET
    return render_template('verify_otp.html', phone=phone, purpose=purpose)


# --- بوابة إنشاء حساب للعميل (إيميل) ---
@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if not email or not password:
            flash('يرجى تعبئة البريد وكلمة المرور', 'danger')
            return render_template('signup.html')
        if password != confirm:
            flash('الرجاء التأكد من تطابق كلمات المرور', 'danger')
            return render_template('signup.html')
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مسجل مسبقًا', 'danger')
            return render_template('signup.html')

        user = User(name=name or email.split('@')[0], email=email, role='client')
        user.set_password(password)
        user.email_verified = False
        db.session.add(user)
        db.session.commit()
        flash('تم إنشاء الحساب بنجاح. يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('auth.login'))

    return render_template('signup.html')


# --- Google OAuth ---
@auth.route('/login/google')
def login_google():
    oauth = get_oauth()
    redirect_uri = url_for('auth.google_callback', _external=True)
    print("Redirect URI:", redirect_uri)  # ✅ أضف هذا السطر لمراجعة الرابط الحقيقي
    return oauth.google.authorize_redirect(redirect_uri)



@auth.route('/auth/google/callback')
def google_callback():
    oauth = get_oauth()
    token = oauth.google.authorize_access_token()
    userinfo = token.get('userinfo') or oauth.google.parse_id_token(token)
    if not userinfo:
        flash('تعذر الحصول على بيانات Google', 'danger')
        return redirect(url_for('auth.login'))

    email = (userinfo.get('email') or '').lower()
    sub = userinfo.get('sub')
    name = userinfo.get('name') or email.split('@')[0]
    email_verified = bool(userinfo.get('email_verified'))

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email, role='client', oauth_provider='google', oauth_subject=sub, email_verified=email_verified)
        # set a random password placeholder
        user.set_password(secrets.token_urlsafe(16))
        db.session.add(user)
        db.session.commit()
    else:
        # Link account if not already linked
        if not user.oauth_provider:
            user.oauth_provider = 'google'
            user.oauth_subject = sub
            if email_verified:
                user.email_verified = True
            db.session.commit()

    login_user(user)
    flash('تم تسجيل الدخول عبر Google', 'success')
    return redirect(url_for('main.landing'))


# --- Apple OAuth ---
@auth.route('/login/apple')
def login_apple():
    oauth = get_oauth()
    redirect_uri = url_for('auth.apple_callback', _external=True)
    return oauth.apple.authorize_redirect(redirect_uri)


@auth.route('/auth/apple/callback', methods=['GET', 'POST'])
def apple_callback():
    oauth = get_oauth()
    token = oauth.apple.authorize_access_token()
    id_token = token.get('id_token')
    claims = oauth.apple.parse_id_token(token) if id_token else None
    if not claims:
        flash('تعذر الحصول على بيانات Apple', 'danger')
        return redirect(url_for('auth.login'))

    email = (claims.get('email') or '').lower()
    sub = claims.get('sub')
    name = (claims.get('name') or '') or (email.split('@')[0] if email else 'Apple User')
    email_verified = str(claims.get('email_verified')).lower() == 'true'

    if not email:
        flash('حساب Apple لم يرجع بريد إلكتروني. الرجاء ربط البريد لاحقًا', 'warning')
        # Fallback: construct pseudo email to allow account creation
        email = f"apple-{sub}@private.appleid"

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(name=name, email=email, role='client', oauth_provider='apple', oauth_subject=sub, email_verified=email_verified)
        user.set_password(secrets.token_urlsafe(16))
        db.session.add(user)
        db.session.commit()
    else:
        if not user.oauth_provider:
            user.oauth_provider = 'apple'
            user.oauth_subject = sub
            if email_verified:
                user.email_verified = True
            db.session.commit()

    login_user(user)
    flash('تم تسجيل الدخول عبر Apple', 'success')
    return redirect(url_for('main.landing'))


# --- تسجيل الخروج ---
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج', 'success')
    return redirect(url_for('auth.login'))


# --- التسجيل عبر رابط الدعوة ---
@auth.route('/register', methods=['GET', 'POST'])
def register():
    token_value = request.args.get('token') if request.method == 'GET' else request.form.get('token')
    if not token_value:
        flash('رابط الدعوة غير صالح', 'danger')
        return redirect(url_for('auth.login'))

    invite = InviteToken.query.filter_by(token=token_value).first()
    if not invite:
        flash('رابط الدعوة غير موجود', 'danger')
        return redirect(url_for('auth.login'))
    if invite.used_at is not None:
        flash('تم استخدام رابط الدعوة بالفعل', 'warning')
        return redirect(url_for('auth.login'))
    if invite.expires_at < datetime.utcnow():
        flash('انتهت صلاحية رابط الدعوة', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        name = request.form.get('name') or invite.name or ''
        email = request.form.get('email') or invite.email
        phone = request.form.get('phone') or invite.phone
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if not password or password != confirm:
            flash('الرجاء التأكد من تطابق كلمات المرور', 'danger')
            return render_template('register.html', invite=invite, token=token_value)

        # منع تكرار البريد الإلكتروني
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مسجل مسبقًا', 'danger')
            return render_template('register.html', invite=invite, token=token_value)

        # إنشاء المستخدم حسب الدور
        new_user = User(name=name or email.split('@')[0], email=email, phone=phone, role=invite.role)
        new_user.set_password(password)
        db.session.add(new_user)
        invite.used_at = datetime.utcnow()
        db.session.commit()

        flash('تم إنشاء الحساب بنجاح. يمكنك تسجيل الدخول الآن', 'success')
        return redirect(url_for('auth.login'))

    # GET: عرض نموذج تعبئة البيانات
    return render_template('register.html', invite=invite, token=token_value)
