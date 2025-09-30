from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User

auth = Blueprint('auth', __name__, template_folder='../templates/auth')

# صفحة تسجيل الدخول
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()  # البحث عن المستخدم
        if user and user.check_password(password):  # التحقق من كلمة المرور
            login_user(user)
            flash('تم تسجيل الدخول بنجاح', 'success')
            # إعادة توجيه حسب الدور
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

# تسجيل الخروج
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج', 'success')
    return redirect(url_for('auth.login'))
