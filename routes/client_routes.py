"""Blueprint for client portal routes and templates."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, ValuationRequest

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
    return render_template('client/dashboard.html', requests=reqs)

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
