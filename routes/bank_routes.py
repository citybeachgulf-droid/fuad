from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User, ValuationRequest

# تعريف Blueprint للبنك
bank_bp = Blueprint('bank', __name__, template_folder='templates/bank')

# --- Dashboard للبنك ---
@bank_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'bank':
        return "غير مصرح لك بالوصول", 403

    # جلب الطلبات المخصصة للبنك الحالي
    requests = ValuationRequest.query.filter_by(bank_id=current_user.id).all()
    return render_template('bank/dashboard.html', requests=requests)

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
