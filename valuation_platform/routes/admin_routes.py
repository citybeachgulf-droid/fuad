"""Blueprint for admin portal routes and templates."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, ValuationRequest

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin', static_folder='../static')

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    # Only allow admin role to access in real app; here it's simple demo assume login is admin
    users = User.query.all()
    requests = ValuationRequest.query.order_by(ValuationRequest.created_at.desc()).all()
    return render_template('admin/dashboard.html', users=users, requests=requests)

@admin_bp.route('/assign', methods=['POST'])
@login_required
def assign_request():
    req_id = request.form.get('request_id')
    company_id = request.form.get('company_id')
    vr = ValuationRequest.query.get(req_id)
    if vr:
        vr.company_id = int(company_id)
        db.session.commit()
        flash('Assigned to company', 'success')
    return redirect(url_for('admin.dashboard'))
