from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, User, ValuationRequest, BankProfile, BankOffer, BankLoanPolicy
from utils import calculate_max_loan

# تعريف Blueprint للبنك
bank_bp = Blueprint('bank', __name__, template_folder='templates/bank')

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

    return render_template('bank/dashboard.html', requests=requests, offers=offers, policies=policies)

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
