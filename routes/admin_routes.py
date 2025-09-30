from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, User
from flask_login import login_required, current_user

admin_bp = Blueprint('admin', __name__, template_folder='templates/admin')

# Dashboard (محمي ويعرض البنوك والشركات)
@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    banks = User.query.filter_by(role='bank').all()
    companies = User.query.filter_by(role='company').all()
    return render_template('admin/dashboard.html', banks=banks, companies=companies)

# إضافة بنك
@admin_bp.route('/add_bank', methods=['POST'])
@login_required
def add_bank():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    name = request.form['name']
    email = request.form['email']
    phone = request.form.get('phone')
    new_bank = User(name=name, email=email, phone=phone, role='bank')
    db.session.add(new_bank)
    db.session.commit()
    flash('تم إضافة البنك بنجاح', 'success')
    return redirect(url_for('admin.dashboard'))

# إضافة شركة تثمين
@admin_bp.route('/add_company', methods=['POST'])
@login_required
def add_company():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    name = request.form['name']
    email = request.form['email']
    phone = request.form.get('phone')
    new_company = User(name=name, email=email, phone=phone, role='company')
    db.session.add(new_company)
    db.session.commit()
    flash('تم إضافة الشركة بنجاح', 'success')
    return redirect(url_for('admin.dashboard'))
