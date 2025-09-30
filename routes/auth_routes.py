from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, InviteToken
from datetime import datetime

# Blueprint مع مسار صحيح لمجلد القوالب
auth = Blueprint('auth', __name__, template_folder='../templates/auth')

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
                return redirect(url_for('client.dashboard'))
        else:
            flash('البريد الإلكتروني أو كلمة المرور خاطئة', 'danger')

    return render_template('login.html')


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
