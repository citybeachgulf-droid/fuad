from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, User
from flask_login import login_required, current_user

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin', static_folder='../static')


# --- Dashboard (محمي ويعرض البنوك والشركات) ---
from models import ValuationRequest

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403

    banks = User.query.filter_by(role='bank').all()
    companies = User.query.filter_by(role='company').all()
    clients = User.query.filter_by(role='client').all()
    requests = ValuationRequest.query.all()

    return render_template(
        'dashboard.html',
        banks=banks,
        companies=companies,
        clients=clients,
        requests=requests
    )

# --- إضافة بنك ---
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

# --- إضافة شركة تثمين ---
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

# --- صفحة عرض البنوك ---
@admin_bp.route('/banks')
@login_required
def banks():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    banks = User.query.filter_by(role='bank').all()
    return render_template('banks.html', banks=banks)

# --- صفحة عرض شركات التثمين ---
@admin_bp.route('/companies')
@login_required
def companies():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    companies = User.query.filter_by(role='company').all()
    return render_template('companies.html', companies=companies)
