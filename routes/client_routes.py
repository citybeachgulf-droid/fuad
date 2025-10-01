"""Blueprint for client portal routes and templates."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, ValuationRequest, BankProfile, BankLoanPolicy
from utils import calculate_max_loan

client_bp = Blueprint('client', __name__, template_folder='../templates/client', static_folder='../static')

@client_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Simple login form for demo (no hashing). In production, validate and hash passwords.
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email, password=password, role='client').first()
        if user:
            login_user(user)
            return redirect(url_for('client.dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('client/login.html')

@client_bp.route('/dashboard')
@login_required
def dashboard():
    # show client's requests
    reqs = ValuationRequest.query.filter_by(client_id=current_user.id).all()
    banks = BankProfile.query.order_by(BankProfile.id.asc()).all()
    return render_template('client/dashboard.html', requests=reqs, banks=banks)

@client_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_request():
    # Bring list of companies for selection
    companies = User.query.filter_by(role='company').all()

    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')

        # Company selection (optional but recommended)
        company_id_raw = request.form.get('company_id')
        company_id = None
        if company_id_raw:
            try:
                company_id_candidate = int(company_id_raw)
                # Validate that the selected user is actually a company
                company_user = User.query.filter_by(id=company_id_candidate, role='company').first()
                if company_user:
                    company_id = company_user.id
            except Exception:
                company_id = None

        vr = ValuationRequest(
            title=title,
            description=description,
            client_id=current_user.id,
            company_id=company_id,
        )
        db.session.add(vr)
        db.session.commit()
        flash('Valuation request submitted', 'success')
        return redirect(url_for('client.dashboard'))

    # Preselect company if passed as query parameter from company detail page
    preselected_company_id = request.args.get('company_id', type=int)
    return render_template('client/submit.html', companies=companies, preselected_company_id=preselected_company_id)


# -------------------------------
# APIs for client loan policies and computation
# -------------------------------
@client_bp.route('/loan_policies', methods=['GET'])
@login_required
def get_loan_policies():
    bank_slug = request.args.get('bank_slug')
    loan_type = request.args.get('loan_type')
    if not bank_slug:
        return jsonify({'error': 'bank_slug is required'}), 400
    bank = BankProfile.query.filter_by(slug=bank_slug).first()
    if not bank:
        return jsonify({'error': 'bank not found'}), 404
    query = BankLoanPolicy.query.filter_by(bank_profile_id=bank.id)
    if loan_type:
        query = query.filter_by(loan_type=loan_type)
    policies = query.all()
    return jsonify([
        {
            'loan_type': p.loan_type,
            'max_ratio': p.max_ratio,
            'default_annual_rate': p.default_annual_rate,
            'default_years': p.default_years,
        } for p in policies
    ])


@client_bp.route('/compute_max_loan', methods=['POST'])
@login_required
def compute_max_loan():
    data = request.get_json(silent=True) or request.form
    bank_slug = data.get('bank_slug')
    loan_type = (data.get('loan_type') or 'housing').strip() or 'housing'
    try:
        income = float(data.get('income', '0') or 0)
    except Exception:
        income = 0.0
    annual_rate = data.get('annual_rate')
    years = data.get('years')

    # Resolve policy and enforce server-side max_ratio
    bank = BankProfile.query.filter_by(slug=bank_slug).first() if bank_slug else None
    if not bank:
        return jsonify({'error': 'bank not found'}), 404
    policy = BankLoanPolicy.query.filter_by(bank_profile_id=bank.id, loan_type=loan_type).first()
    if not policy:
        return jsonify({'error': 'policy not found for bank and loan_type'}), 404

    # Apply defaults if fields are missing
    if annual_rate in (None, ''):
        annual_rate = policy.default_annual_rate or 0
    else:
        annual_rate = float(annual_rate)
    if years in (None, ''):
        years = policy.default_years or 0
    else:
        years = int(years)

    principal, max_payment = calculate_max_loan(income, float(annual_rate), int(years), float(policy.max_ratio))
    return jsonify({
        'max_principal': principal,
        'max_monthly_payment': max_payment,
        'used': {
            'annual_rate': float(annual_rate),
            'years': int(years),
            'max_ratio': float(policy.max_ratio)
        }
    })
