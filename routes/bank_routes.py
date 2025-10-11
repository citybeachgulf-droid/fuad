from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import db, User, ValuationRequest, BankProfile, BankOffer, BankLoanPolicy, CompanyApprovedBank, CompanyProfile
from utils import calculate_max_loan
from werkzeug.utils import secure_filename
import os
import time

# تعريف Blueprint للبنك
bank_bp = Blueprint('bank', __name__, template_folder='templates/bank')

# --- Logo upload helpers ---
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_LOGO_EXTENSIONS

# --- Dashboard للبنك ---
@bank_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403

    # التأكد من وجود ملف تعريف للبنك أو إنشاؤه بشكل مبسط
    bank_profile = current_user.bank_profile
    if bank_profile is None:
        # إنشاء ملف تعريف أساسي للبنك إذا لم يكن موجودًا
        bank_profile = BankProfile(
            user_id=current_user.id,
            slug=f"bank-{current_user.id}"
        )
        db.session.add(bank_profile)
        db.session.commit()

    # جلب الطلبات المخصصة للبنك الحالي
    requests = ValuationRequest.query.filter_by(bank_id=current_user.id).all()

    # جلب عروض البنك
    offers = bank_profile.offers if bank_profile else []

    # جلب سياسات القروض الحالية
    policies = BankLoanPolicy.query.filter_by(bank_profile_id=bank_profile.id).all()

    # جلب الشركات المعتمدة لدى هذا البنك
    approved_rows = (
        db.session.query(CompanyApprovedBank, CompanyProfile, User)
        .join(CompanyProfile, CompanyApprovedBank.company_profile_id == CompanyProfile.id)
        .join(User, CompanyProfile.user_id == User.id)
        .filter(CompanyApprovedBank.bank_user_id == current_user.id)
        .all()
    )
    approved_companies = [
        {
            'cab_id': cab.id,
            'company_user_id': user.id,
            'name': user.name,
            'limit_value': (cab.limit_value if cab.limit_value is not None else profile.limit_value),
            'logo_path': profile.logo_path,
        }
        for cab, profile, user in approved_rows
    ]

    # جميع شركات التثمين غير المعتمدة بعد من هذا البنك
    approved_user_ids = {item['company_user_id'] for item in approved_companies}
    companies_all = (
        db.session.query(User, CompanyProfile)
        .join(CompanyProfile, CompanyProfile.user_id == User.id)
        .filter(User.role == 'company')
        .all()
    )
    companies_to_add = [
        {
            'user_id': user.id,
            'name': user.name,
            'limit_value': profile.limit_value,
        }
        for user, profile in companies_all
        if user.id not in approved_user_ids
    ]

    return render_template(
        'bank/dashboard.html',
        requests=requests,
        offers=offers,
        policies=policies,
        approved_companies=approved_companies,
        companies_to_add=companies_to_add,
        bank_profile=bank_profile,
    )


# --- إدارة الشركات المعتمدة للبنك ---
@bank_bp.route('/approved_companies/add', methods=['POST'])
@login_required
def add_approved_company():
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403

    try:
        company_user_id = int(request.form.get('company_user_id'))
    except Exception:
        flash('شركة غير صالحة', 'danger')
        return redirect(url_for('bank.dashboard'))

    limit_raw = request.form.get('limit_value')
    limit_value = None
    if limit_raw not in (None, ''):
        try:
            limit_value = float(limit_raw)
        except Exception:
            flash('قيمة حد غير صالحة', 'danger')
            return redirect(url_for('bank.dashboard'))

    profile = CompanyProfile.query.filter_by(user_id=company_user_id).first()
    if not profile:
        flash('ملف الشركة غير موجود', 'danger')
        return redirect(url_for('bank.dashboard'))

    cab = CompanyApprovedBank.query.filter_by(company_profile_id=profile.id, bank_user_id=current_user.id).first()
    if not cab:
        cab = CompanyApprovedBank(company_profile_id=profile.id, bank_user_id=current_user.id, limit_value=limit_value)
        db.session.add(cab)
    else:
        cab.limit_value = limit_value
    db.session.commit()
    flash('تم اعتماد الشركة بنجاح', 'success')
    return redirect(url_for('bank.dashboard'))


@bank_bp.route('/approved_companies/<int:cab_id>/delete', methods=['POST'])
@login_required
def delete_approved_company(cab_id: int):
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403
    cab = CompanyApprovedBank.query.get_or_404(cab_id)
    if cab.bank_user_id != current_user.id:
        return "غير مصرح لك بالوصول", 403
    db.session.delete(cab)
    db.session.commit()
    flash('تم إزالة اعتماد الشركة', 'success')
    return redirect(url_for('bank.dashboard'))


@bank_bp.route('/approved_companies/<int:cab_id>/update', methods=['POST'])
@login_required
def update_approved_company(cab_id: int):
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403
    cab = CompanyApprovedBank.query.get_or_404(cab_id)
    if cab.bank_user_id != current_user.id:
        return "غير مصرح لك بالوصول", 403
    limit_raw = request.form.get('limit_value')
    limit_value = None
    if limit_raw not in (None, ''):
        try:
            limit_value = float(limit_raw)
        except Exception:
            flash('قيمة حد غير صالحة', 'danger')
            return redirect(url_for('bank.dashboard'))
    cab.limit_value = limit_value
    db.session.commit()
    flash('تم تحديث حد الشركة', 'success')
    return redirect(url_for('bank.dashboard'))


# --- تحديث شعار البنك ---
@bank_bp.route('/profile/logo', methods=['POST'])
@login_required
def update_logo():
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403

    bank_profile = current_user.bank_profile
    if bank_profile is None:
        bank_profile = BankProfile(
            user_id=current_user.id,
            slug=f"bank-{current_user.id}"
        )
        db.session.add(bank_profile)
        db.session.commit()

    file = request.files.get('logo')
    if not file or not file.filename:
        flash('الرجاء اختيار ملف شعار', 'danger')
        return redirect(url_for('bank.dashboard'))
    if not _allowed_file(file.filename):
        flash('صيغة الشعار غير مدعومة', 'danger')
        return redirect(url_for('bank.dashboard'))

    upload_folder = current_app.config.get('UPLOAD_FOLDER')
    os.makedirs(upload_folder, exist_ok=True)
    filename = f"bank_{current_user.id}_{int(time.time())}_" + secure_filename(file.filename)
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    rel_path = os.path.relpath(file_path, os.path.join(current_app.root_path, 'static'))
    bank_profile.logo_path = rel_path.replace('\\', '/')
    db.session.commit()

    flash('تم تحديث شعار البنك', 'success')
    return redirect(url_for('bank.dashboard'))

# --- تحديث حالة الطلب ---
@bank_bp.route('/update_request/<int:request_id>', methods=['POST'])
@login_required
def update_request(request_id):
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403

    req = ValuationRequest.query.get_or_404(request_id)
    if req.bank_id != current_user.id:
        return "غير مصرح لك بالوصول", 403

    new_status = request.form.get('status')
    req.status = new_status
    db.session.commit()
    flash('تم تحديث حالة الطلب', 'success')
    return redirect(url_for('bank.dashboard'))


# --- إدارة سياسات القروض للبنك ---
@bank_bp.route('/policies', methods=['GET'])
@login_required
def list_policies():
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403
    bank_profile = current_user.bank_profile
    if not bank_profile:
        return jsonify([])
    items = BankLoanPolicy.query.filter_by(bank_profile_id=bank_profile.id).all()
    return jsonify([
        {
            'id': p.id,
            'loan_type': p.loan_type,
            'max_ratio': p.max_ratio,
            'default_annual_rate': p.default_annual_rate,
            'default_years': p.default_years,
        } for p in items
    ])


@bank_bp.route('/policies/upsert', methods=['POST'])
@login_required
def upsert_policy():
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403
    bank_profile = current_user.bank_profile
    if bank_profile is None:
        bank_profile = BankProfile(
            user_id=current_user.id,
            slug=f"bank-{current_user.id}"
        )
        db.session.add(bank_profile)
        db.session.commit()

    loan_type = request.form.get('loan_type', 'housing').strip() or 'housing'
    try:
        max_ratio = float(request.form.get('max_ratio'))
    except Exception:
        max_ratio = 0.4
    default_annual_rate = request.form.get('default_annual_rate')
    default_years = request.form.get('default_years')
    default_annual_rate = float(default_annual_rate) if default_annual_rate not in (None, '',) else None
    default_years = int(default_years) if default_years not in (None, '',) else None

    policy = BankLoanPolicy.query.filter_by(bank_profile_id=bank_profile.id, loan_type=loan_type).first()
    if not policy:
        policy = BankLoanPolicy(
            bank_profile_id=bank_profile.id,
            loan_type=loan_type,
            max_ratio=max_ratio,
            default_annual_rate=default_annual_rate,
            default_years=default_years,
        )
        db.session.add(policy)
    else:
        policy.max_ratio = max_ratio
        policy.default_annual_rate = default_annual_rate
        policy.default_years = default_years

    db.session.commit()
    flash('تم حفظ سياسة القرض', 'success')
    return redirect(url_for('bank.dashboard'))


# --- API لحساب أقصى قرض ممكن للعرض للعميل ---
@bank_bp.route('/compute_max_loan', methods=['POST'])
@login_required
def compute_max_loan_api():
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403
    income = float(request.form.get('income', '0') or 0)
    annual_rate = float(request.form.get('annual_rate', '0') or 0)
    years = int(request.form.get('years', '0') or 0)
    max_ratio = float(request.form.get('max_ratio', '0') or 0)
    P, max_payment = calculate_max_loan(income, annual_rate, years, max_ratio)
    return jsonify({
        'max_principal': P,
        'max_monthly_payment': max_payment
    })


# --- إضافة عرض تمويلي للبنك ---
@bank_bp.route('/offers/add', methods=['POST'])
@login_required
def add_offer():
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403

    bank_profile = current_user.bank_profile
    if bank_profile is None:
        bank_profile = BankProfile(
            user_id=current_user.id,
            slug=f"bank-{current_user.id}"
        )
        db.session.add(bank_profile)
        db.session.commit()

    product_name = request.form.get('product_name') or 'تمويل'
    rate_type = request.form.get('rate_type') or None
    try:
        interest_rate = float(request.form.get('interest_rate', '0') or 0)
    except ValueError:
        interest_rate = 0.0
    try:
        apr = float(request.form.get('apr') or 0)
    except ValueError:
        apr = None
    try:
        min_amount = float(request.form.get('min_amount') or 0) or None
    except ValueError:
        min_amount = None
    try:
        max_amount = float(request.form.get('max_amount') or 0) or None
    except ValueError:
        max_amount = None
    try:
        min_tenure_months = int(request.form.get('min_tenure_months') or 0) or None
    except ValueError:
        min_tenure_months = None
    try:
        max_tenure_months = int(request.form.get('max_tenure_months') or 0) or None
    except ValueError:
        max_tenure_months = None
    notes = request.form.get('notes') or None

    offer = BankOffer(
        bank_profile_id=bank_profile.id,
        product_name=product_name,
        rate_type=rate_type,
        interest_rate=interest_rate,
        apr=apr,
        min_amount=min_amount,
        max_amount=max_amount,
        min_tenure_months=min_tenure_months,
        max_tenure_months=max_tenure_months,
        notes=notes,
    )

    db.session.add(offer)
    db.session.commit()
    flash('تم إضافة العرض بنجاح', 'success')
    return redirect(url_for('bank.dashboard'))
