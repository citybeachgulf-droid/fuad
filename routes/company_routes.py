"""Blueprint for valuation company portal routes and templates."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, ValuationRequest

company_bp = Blueprint('company', __name__, template_folder='../templates/company', static_folder='../static')

@company_bp.route('/dashboard')
@login_required
def dashboard():
    # show requests assigned to this company (demo)
    reqs = ValuationRequest.query.filter_by(company_id=current_user.id).all()
    return render_template('company/dashboard.html', requests=reqs)

@company_bp.route('/submit/<int:request_id>', methods=['GET', 'POST'])
@login_required
def submit_valuation(request_id):
    vr = ValuationRequest.query.get(request_id)
    if request.method == 'POST':
        vr.value = float(request.form.get('value') or 0)
        vr.status = 'completed'
        db.session.commit()
        flash('Valuation submitted', 'success')
        return redirect(url_for('company.dashboard'))
    return render_template('company/submit.html', request_obj=vr)
