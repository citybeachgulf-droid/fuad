"""Blueprint for bank portal routes and templates."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, ValuationRequest

bank_bp = Blueprint('bank', __name__, template_folder='../templates/bank', static_folder='../static')

@bank_bp.route('/dashboard')
@login_required
def dashboard():
    # show valuations for bank review
    reqs = ValuationRequest.query.filter_by(bank_id=current_user.id).all()
    return render_template('bank/dashboard.html', requests=reqs)

@bank_bp.route('/review/<int:request_id>', methods=['POST'])
@login_required
def review(request_id):
    action = request.form.get('action')
    vr = ValuationRequest.query.get(request_id)
    if not vr:
        flash('Request not found', 'danger')
        return redirect(url_for('bank.dashboard'))
    if action == 'approve':
        vr.status = 'approved'
    elif action == 'revision':
        vr.status = 'revision_requested'
    db.session.commit()
    flash('Action recorded', 'success')
    return redirect(url_for('bank.dashboard'))
