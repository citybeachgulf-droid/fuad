"""Blueprint for valuation company portal routes and templates."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db, ValuationRequest, CompanyProfile, User, CompanyApprovedBank, CompanyContact
from werkzeug.utils import secure_filename
import os
import time

company_bp = Blueprint('company', __name__, template_folder='templates/company')

@company_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'company':
        return "غير مصرح لك بالوصول", 403
    # جلب الطلبات المرتبطة بالشركة
    requests = ValuationRequest.query.filter_by(company_id=current_user.id).all()
    profile = CompanyProfile.query.filter_by(user_id=current_user.id).first()
    return render_template('company/dashboard.html', requests=requests, profile=profile)

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


# ================================
# إدارة ملف تعريف الشركة
# ================================
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_LOGO_EXTENSIONS


@company_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if current_user.role != 'company':
        return "غير مصرح لك بالوصول", 403

    profile = CompanyProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        profile = CompanyProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()

    # جلب البنوك وأرقام التواصل الحالية
    banks = User.query.filter_by(role='bank').all()
    approved_bank_ids = [ab.bank_user_id for ab in getattr(profile, 'approved_banks', [])]
    contacts_list = list(getattr(profile, 'contacts', []))

    if request.method == 'POST':
        services = request.form.get('services') or None
        limit_value_raw = request.form.get('limit_value')
        about = request.form.get('about') or None
        website = request.form.get('website') or None

        try:
            limit_value = float(limit_value_raw) if limit_value_raw else None
        except ValueError:
            flash('الرجاء إدخال قيمة حد صحيحة', 'danger')
            return render_template('company/profile_edit.html', profile=profile, banks=banks, approved_bank_ids=approved_bank_ids, contacts=contacts_list)

        # معالجة رفع الشعار
        file = request.files.get('logo')
        if file and file.filename:
            if not _allowed_file(file.filename):
                flash('صيغة الشعار غير مدعومة', 'danger')
                return render_template('company/profile_edit.html', profile=profile, banks=banks, approved_bank_ids=approved_bank_ids, contacts=contacts_list)
            upload_folder = current_app.config.get('UPLOAD_FOLDER')
            os.makedirs(upload_folder, exist_ok=True)
            filename = f"company_{current_user.id}_{int(time.time())}_" + secure_filename(file.filename)
            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)
            # حفظ المسار النسبي ضمن مجلد static لعرضه
            rel_path = os.path.relpath(file_path, os.path.join(current_app.root_path, 'static'))
            profile.logo_path = rel_path.replace('\\', '/')

        profile.services = services
        profile.limit_value = limit_value
        profile.about = about
        profile.website = website

        # تحديث البنوك المعتمدة
        selected_bank_ids_raw = request.form.getlist('approved_banks')
        try:
            selected_bank_ids = [int(bid) for bid in selected_bank_ids_raw if bid]
        except Exception:
            selected_bank_ids = []

        # امسح الحالي ثم أضف الجديد
        if hasattr(profile, 'approved_banks'):
            profile.approved_banks.clear()
        for bank_id in selected_bank_ids:
            profile.approved_banks.append(CompanyApprovedBank(bank_user_id=bank_id))

        # تحديث أرقام التواصل
        labels = request.form.getlist('contact_label')
        phones = request.form.getlist('contact_phone')
        if hasattr(profile, 'contacts'):
            profile.contacts.clear()
        for label, phone in zip(labels, phones):
            phone_value = (phone or '').strip()
            label_value = (label or '').strip() or None
            if phone_value:
                profile.contacts.append(CompanyContact(label=label_value, phone=phone_value))
        db.session.commit()
        flash('تم حفظ الملف التعريفي بنجاح', 'success')
        return redirect(url_for('company.edit_profile'))

    # تمرير البيانات إلى الواجهة
    approved_bank_ids = [ab.bank_user_id for ab in getattr(profile, 'approved_banks', [])]
    contacts_list = list(getattr(profile, 'contacts', []))
    return render_template('company/profile_edit.html', profile=profile, banks=banks, approved_bank_ids=approved_bank_ids, contacts=contacts_list)
