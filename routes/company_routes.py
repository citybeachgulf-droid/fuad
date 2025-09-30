"""Blueprint for valuation company portal routes and templates."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from models import db, ValuationRequest, CompanyProfile, CompanyManualBank, CompanyContact
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

    # جلب بيانات أرقام التواصل والبنوك اليدوية
    contacts_list = list(getattr(profile, 'contacts', []))
    manual_banks_list = list(getattr(profile, 'manual_banks', []))

    if request.method == 'POST':
        services = request.form.get('services') or None
        limit_value_raw = request.form.get('limit_value')
        about = request.form.get('about') or None
        website = request.form.get('website') or None

        try:
            limit_value = float(limit_value_raw) if limit_value_raw else None
        except ValueError:
            flash('الرجاء إدخال قيمة حد صحيحة للحد العام', 'danger')
            return render_template('company/profile_edit.html', profile=profile, contacts=contacts_list, manual_banks=manual_banks_list)

        # معالجة رفع الشعار
        file = request.files.get('logo')
        if file and file.filename:
            if not _allowed_file(file.filename):
                flash('صيغة الشعار غير مدعومة', 'danger')
                return render_template('company/profile_edit.html', profile=profile, contacts=contacts_list, manual_banks=manual_banks_list)
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

        # تحديث البنوك اليدوية
        names = request.form.getlist('bank_name')
        emails = request.form.getlist('bank_email')
        phones = request.form.getlist('bank_phone')
        limits = request.form.getlist('bank_limit')

        posted_manual_banks = []
        has_limit_error = False
        for name_val, email_val, phone_val, limit_val in zip(names, emails, phones, limits):
            name_clean = (name_val or '').strip()
            email_clean = (email_val or '').strip() or None
            phone_clean = (phone_val or '').strip() or None
            limit_clean = None
            if not name_clean and not email_clean and not phone_clean and (limit_val or '').strip() == '':
                # صف فارغ بالكامل — تجاهله
                continue
            if not name_clean:
                # يلزم الاسم لحفظ البنك
                has_limit_error = True
                flash('الرجاء كتابة اسم البنك لكل صف غير فارغ', 'danger')
            limit_str = (limit_val or '').strip()
            if limit_str:
                try:
                    limit_clean = float(limit_str)
                except ValueError:
                    has_limit_error = True
                    flash(f'قيمة حد غير صالحة للبنك: {name_clean or "(بدون اسم)"}', 'danger')
            posted_manual_banks.append({
                'name': name_clean,
                'email': email_clean,
                'phone': phone_clean,
                'limit_value': limit_clean if not has_limit_error else limit_str
            })

        if has_limit_error:
            # أعد العرض مع القيم المدخلة
            return render_template('company/profile_edit.html', profile=profile, contacts=contacts_list, manual_banks=posted_manual_banks)

        # استبدل القائمة الحالية
        if hasattr(profile, 'manual_banks'):
            profile.manual_banks.clear()
        for b in posted_manual_banks:
            if b.get('name'):
                profile.manual_banks.append(CompanyManualBank(
                    name=b.get('name'),
                    email=b.get('email'),
                    phone=b.get('phone'),
                    limit_value=b.get('limit_value')
                ))

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
    contacts_list = list(getattr(profile, 'contacts', []))
    manual_banks_list = list(getattr(profile, 'manual_banks', []))
    return render_template('company/profile_edit.html', profile=profile, contacts=contacts_list, manual_banks=manual_banks_list)
