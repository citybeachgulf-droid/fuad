"""Blueprint for client portal routes and templates."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, ValuationRequest, BankProfile, BankLoanPolicy, RequestDocument, VisitAppointment, Conversation, Message, ActivityLog
from werkzeug.utils import secure_filename
import os
import time
from utils import calculate_max_loan, format_phone_e164, store_file_and_get_url
from datetime import datetime

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
            return redirect(url_for('client.profile'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('client/login.html')

@client_bp.route('/profile')
@login_required
def profile():
    """عرض ملف العميل الشخصي بعد تسجيل الدخول."""
    return render_template('client/profile.html', user=current_user)


@client_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """تعديل بيانات ملف العميل الشخصي."""
    if current_user.role != 'client':
        return "غير مصرح لك بالوصول", 403

    user = current_user

    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        phone_raw = (request.form.get('phone') or '').strip()

        current_password = request.form.get('current_password') or ''
        new_password = request.form.get('new_password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        if not name:
            flash('يرجى إدخال الاسم', 'danger')
            return render_template('client/profile_edit.html', user=user)

        if not email:
            flash('يرجى إدخال البريد الإلكتروني', 'danger')
            return render_template('client/profile_edit.html', user=user)

        # التحقق من فريدة البريد الإلكتروني عند تغييره
        if email != (user.email or '').lower():
            exists = User.query.filter(User.email == email, User.id != user.id).first()
            if exists:
                flash('البريد الإلكتروني مستخدم بالفعل', 'danger')
                return render_template('client/profile_edit.html', user=user)

        # توحيد تنسيق الهاتف
        phone = format_phone_e164(phone_raw) if phone_raw else None

        # تغيير كلمة المرور (اختياري)
        if new_password or confirm_password:
            if new_password != confirm_password:
                flash('كلمتا المرور غير متطابقتين', 'danger')
                return render_template('client/profile_edit.html', user=user)
            # طلب كلمة المرور الحالية للتحقق، مع استثناء حسابات OAuth التي لا تملك كلمة معروفة
            if not (user.oauth_provider and not current_password):
                if not user.check_password(current_password):
                    flash('كلمة المرور الحالية غير صحيحة', 'danger')
                    return render_template('client/profile_edit.html', user=user)
            user.set_password(new_password)

        email_changed = email != (user.email or '').lower()
        user.name = name
        user.email = email
        user.phone = phone
        if email_changed:
            user.email_verified = False

        db.session.commit()
        flash('تم تحديث الملف الشخصي', 'success')
        return redirect(url_for('client.profile'))

    return render_template('client/profile_edit.html', user=user)

@client_bp.route('/dashboard')
@login_required
def dashboard():
    # show client's requests
    reqs = ValuationRequest.query.filter_by(client_id=current_user.id).all()
    banks = BankProfile.query.order_by(BankProfile.id.asc()).all()
    return render_template('client/dashboard.html', requests=reqs, banks=banks)


# -------------------------------
# Client request details + transfer
# -------------------------------
@client_bp.route('/requests/<int:request_id>')
@login_required
def request_detail(request_id: int):
    if current_user.role != 'client':
        return "غير مصرح لك بالوصول", 403

    vr = ValuationRequest.query.get_or_404(request_id)
    if vr.client_id != current_user.id:
        return "غير مصرح لك بالوصول", 403

    # استخراج آخر ملاحظة من شركة التثمين عن "مستندات ناقصة" لهذا الطلب (إن وُجدت)
    missing_docs_note = None
    missing_docs_time = None
    try:
        if (vr.status or '').lower() == 'revision_requested' and vr.company_id:
            conv = Conversation.query.filter_by(client_id=current_user.id, company_id=vr.company_id).first()
            if conv:
                # ابحث عن آخر رسالة تخص هذا الطلب تشير إلى مستندات ناقصة
                pattern_part = f"#{vr.id}"
                q = (
                    Message.query
                    .filter(
                        Message.conversation_id == conv.id,
                        Message.content.like('%طلب مستندات ناقصة%'),
                        Message.content.like(f'%{pattern_part}%'),
                    )
                    .order_by(Message.timestamp.desc())
                )
                last_msg = q.first()
                if last_msg:
                    content = last_msg.content or ''
                    # استخرج الملاحظات بعد أول سطر أو بعد النقطتين إن وُجدتا
                    if '\n' in content:
                        missing_docs_note = content.split('\n', 1)[1].strip() or None
                    else:
                        # محاولة إزالة المقدمة الثابتة والإبقاء على الملاحظة فقط
                        split_marker = 'طلب مستندات ناقصة'
                        if split_marker in content:
                            possible = content.split(':', 1)
                            missing_docs_note = (possible[1] if len(possible) > 1 else '').strip() or None
                        else:
                            missing_docs_note = content.strip() or None
                    missing_docs_time = last_msg.timestamp
    except Exception:
        # لا نفشل صفحة التفاصيل إن تعذّر استخراج الرسالة
        missing_docs_note = None
        missing_docs_time = None

    companies = User.query.filter_by(role='company').all()
    return render_template(
        'client/request_detail.html',
        request_obj=vr,
        companies=companies,
        missing_docs_note=missing_docs_note,
        missing_docs_time=missing_docs_time,
    )


@client_bp.route('/requests/<int:request_id>/transfer', methods=['POST'])
@login_required
def transfer_request(request_id: int):
    if current_user.role != 'client':
        return "غير مصرح لك بالوصول", 403

    vr = ValuationRequest.query.get_or_404(request_id)
    if vr.client_id != current_user.id:
        return "غير مصرح لك بالوصول", 403

    # Disallow transferring a completed valuation
    if (vr.status or '').lower() == 'completed':
        flash('لا يمكن تحويل معاملة مكتملة', 'warning')
        return redirect(url_for('client.request_detail', request_id=vr.id))

    company_id_raw = request.form.get('company_id')
    try:
        new_company_id = int(company_id_raw) if company_id_raw else None
    except Exception:
        new_company_id = None

    new_company = User.query.filter_by(id=new_company_id, role='company').first() if new_company_id else None
    if not new_company:
        flash('يرجى اختيار شركة صحيحة', 'danger')
        return redirect(url_for('client.request_detail', request_id=vr.id))

    if vr.company_id == new_company.id:
        flash('المعاملة مخصّصة لهذه الشركة بالفعل', 'info')
        return redirect(url_for('client.request_detail', request_id=vr.id))

    # Apply transfer
    vr.company_id = new_company.id
    vr.status = 'pending'
    # Remove any scheduled/proposed appointments tied to the old company context
    VisitAppointment.query.filter_by(valuation_request_id=vr.id).delete()

    db.session.commit()
    flash('تم تحويل المعاملة إلى الشركة الجديدة', 'success')
    return redirect(url_for('client.request_detail', request_id=vr.id))


# -------------------------------
# Client decision on submitted valuation (accept / decline)
# -------------------------------
@client_bp.route('/requests/<int:request_id>/accept_valuation', methods=['POST'])
@login_required
def accept_valuation(request_id: int):
    if current_user.role != 'client':
        return "غير مصرح لك بالوصول", 403

    vr = ValuationRequest.query.get_or_404(request_id)
    if vr.client_id != current_user.id:
        return "غير مصرح لك بالوصول", 403

    # Allow acceptance only if company has submitted a valuation
    if (vr.status or '').lower() != 'completed':
        flash('لا يمكن قبول التثمين قبل إكماله من الشركة', 'warning')
        return redirect(url_for('client.request_detail', request_id=vr.id))

    vr.status = 'approved'
    try:
        # Notify company via conversation (optional but helpful)
        if vr.company_id:
            conv = Conversation.query.filter_by(client_id=vr.client_id, company_id=vr.company_id).first()
            if not conv:
                conv = Conversation(client_id=vr.client_id, company_id=vr.company_id, status='open')
                db.session.add(conv)
                db.session.flush()
                db.session.add(ActivityLog(conversation_id=conv.id, actor_id=current_user.id, action='conversation_created'))
            value_text = (str(vr.value) if vr.value is not None else '-')
            content = f"قبِل العميل التثمين الخاص بالطلب #{vr.id}. القيمة: {value_text}"
            db.session.add(Message(conversation_id=conv.id, sender_id=current_user.id, content=content))
            db.session.add(ActivityLog(conversation_id=conv.id, actor_id=current_user.id, action='message_sent'))

        db.session.commit()
        flash('تم قبول التثمين. يمكنك الآن تحديد موعد الزيارة.', 'success')
    except Exception:
        db.session.rollback()
        flash('تعذّر تنفيذ العملية. حاول مرة أخرى.', 'danger')

    return redirect(url_for('client.request_detail', request_id=vr.id))


@client_bp.route('/requests/<int:request_id>/decline_valuation', methods=['POST'])
@login_required
def decline_valuation(request_id: int):
    if current_user.role != 'client':
        return "غير مصرح لك بالوصول", 403

    vr = ValuationRequest.query.get_or_404(request_id)
    if vr.client_id != current_user.id:
        return "غير مصرح لك بالوصول", 403

    # Allow decline only if company has submitted a valuation
    if (vr.status or '').lower() != 'completed':
        flash('لا يمكن رفض التثمين قبل إكماله من الشركة', 'warning')
        return redirect(url_for('client.request_detail', request_id=vr.id))

    # Reopen the request with the same company for potential revisions
    vr.status = 'pending'
    try:
        if vr.company_id:
            conv = Conversation.query.filter_by(client_id=vr.client_id, company_id=vr.company_id).first()
            if not conv:
                conv = Conversation(client_id=vr.client_id, company_id=vr.company_id, status='open')
                db.session.add(conv)
                db.session.flush()
                db.session.add(ActivityLog(conversation_id=conv.id, actor_id=current_user.id, action='conversation_created'))
            value_text = (str(vr.value) if vr.value is not None else '-')
            content = f"رفض العميل التثمين الخاص بالطلب #{vr.id}. القيمة المقترحة: {value_text}"
            db.session.add(Message(conversation_id=conv.id, sender_id=current_user.id, content=content))
            db.session.add(ActivityLog(conversation_id=conv.id, actor_id=current_user.id, action='message_sent'))

        db.session.commit()
        flash('تم رفض التثمين وإعادة المعاملة للمراجعة.', 'info')
    except Exception:
        db.session.rollback()
        flash('تعذّر تنفيذ العملية. حاول مرة أخرى.', 'danger')

    return redirect(url_for('client.request_detail', request_id=vr.id))

@client_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_request():
    # Bring list of companies for selection
    companies = User.query.filter_by(role='company').all()
    # Preserve company preselection (if arriving from company details page)
    preselected_company_id = request.args.get('company_id', type=int)

    # Fast-path: allow GET with valuation_type + optional company_id to auto-create and go to docs
    if request.method == 'GET':
        valuation_type_q = (request.args.get('valuation_type') or '').strip()
        if valuation_type_q:
            # Sanitize valuation type
            allowed_types = {'property', 'land', 'house'}
            if valuation_type_q not in allowed_types:
                flash('نوع التثمين غير صالح', 'danger')
                # Show selectable cards (links) to choose a valid type -> redirect directly to property inputs
                options = [
                    {"title": "تثمين عقار قائم", "href": url_for('main.certified_property_inputs', entity='person', purpose='تثمين عقار قائم')},
                    {"title": "تثمين أرض", "href": url_for('main.certified_property_inputs', entity='person', purpose='تثمين أرض')},
                    {"title": "تثمين بناء عقار", "href": url_for('main.certified_property_inputs', entity='person', purpose='تثمين بناء عقار')},
                ]
                return render_template('certified_steps/step_purpose.html', options=options, companies=companies, preselected_company_id=preselected_company_id)

            # Map selected valuation_type to Certified flow purpose and redirect to property inputs
            purpose_map = {
                'property': 'تثمين عقار قائم',
                'land': 'تثمين أرض',
                'house': 'تثمين بناء عقار',
            }
            purpose_value = purpose_map.get(valuation_type_q, 'تثمين عقار قائم')
            return redirect(url_for('main.certified_property_inputs', entity='person', purpose=purpose_value))

        # No type preselected: render cards to pick a type (auto-advances via GET)
        options = [
            {"title": "تثمين عقار قائم", "href": url_for('main.certified_property_inputs', entity='person', purpose='تثمين عقار قائم')},
            {"title": "تثمين أرض", "href": url_for('main.certified_property_inputs', entity='person', purpose='تثمين أرض')},
            {"title": "تثمين بناء عقار", "href": url_for('main.certified_property_inputs', entity='person', purpose='تثمين بناء عقار')},
        ]
        return render_template('certified_steps/step_purpose.html', options=options, companies=companies, preselected_company_id=preselected_company_id)

    if request.method == 'POST':
        # Step 1: Only valuation type (guided) -> redirect to property inputs flow
        valuation_type = (request.form.get('valuation_type') or '').strip() or None
        purpose_map = {
            'property': 'تثمين عقار قائم',
            'land': 'تثمين أرض',
            'house': 'تثمين بناء عقار',
        }
        if valuation_type not in purpose_map:
            flash('يرجى اختيار نوع تثمين صالح', 'danger')
            return redirect(url_for('client.submit_request'))
        purpose_value = purpose_map[valuation_type]
        return redirect(url_for('main.certified_property_inputs', entity='person', purpose=purpose_value))

    # Fallback (should not be reached)
    options = [
        {"title": "تثمين عقار قائم", "href": url_for('main.certified_property_inputs', entity='person', purpose='تثمين عقار قائم')},
        {"title": "تثمين أرض", "href": url_for('main.certified_property_inputs', entity='person', purpose='تثمين أرض')},
        {"title": "تثمين بناء عقار", "href": url_for('main.certified_property_inputs', entity='person', purpose='تثمين بناء عقار')},
    ]
    return render_template('certified_steps/step_purpose.html', options=options, companies=companies, preselected_company_id=preselected_company_id)


# -------------------------------
# Guided documents upload step
# -------------------------------

ALLOWED_DOC_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}

def _allowed_doc(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_DOC_EXTENSIONS


def _required_docs_for_type(valuation_type: str):
    # Returns list of (key, label, icon)
    common_ids = ("ids", "بطاقات هوية", "bi-person-vcard")
    kroki = ("kroki", "كروكي", "bi-map")
    deed = ("deed", "صك الملكية", "bi-file-earmark-text")
    completion = ("completion_certificate", "شهادة إتمام البناء", "bi-patch-check")
    maps = ("maps", "خرائط", "bi-diagram-3")
    contractor = ("contractor_agreement", "اتفاقية المقاول", "bi-file-earmark-richtext")

    if valuation_type == "property":
        return [kroki, deed, completion, maps, common_ids]
    if valuation_type == "land":
        return [kroki, deed, common_ids]
    if valuation_type == "house":
        return [kroki, deed, maps, common_ids, contractor]
    # Default to minimal
    return [common_ids]


@client_bp.route('/submit/docs/<int:request_id>', methods=['GET', 'POST'])
@login_required
def upload_docs(request_id: int):
    vr = ValuationRequest.query.get_or_404(request_id)
    if vr.client_id != current_user.id:
        return "غير مصرح لك بالوصول", 403

    required_docs = _required_docs_for_type(vr.valuation_type or "")

    if request.method == 'POST':
        # Optional: requested valuation amount from bank
        amt_raw = (request.form.get('requested_amount') or '').strip()
        if amt_raw:
            try:
                vr.requested_amount = float(amt_raw.replace(',', ''))
            except Exception:
                flash('تنسيق مبلغ غير صالح', 'danger')
                return render_template('client/upload_docs.html', request_obj=vr, required_docs=required_docs, max_bytes=current_app.config.get('MAX_CONTENT_LENGTH', 5*1024*1024))
        # Ensure each required doc has at least one file
        for key, _, _ in required_docs:
            files = request.files.getlist(f'{key}[]')
            if not files or all((not f or not f.filename) for f in files):
                flash(f'يرجى رفع مستند: {dict((k,l) for k,l,_ in required_docs)[key]}', 'danger')
                return render_template('client/upload_docs.html', request_obj=vr, required_docs=required_docs, max_bytes=current_app.config.get('MAX_CONTENT_LENGTH', 5*1024*1024))

        # Save files (to Backblaze B2 if configured, otherwise local fallback)
        static_root = os.path.join(current_app.root_path, 'static')
        requests_root = os.path.join(static_root, 'uploads', 'requests', f'req_{vr.id}')
        os.makedirs(requests_root, exist_ok=True)

        for key, _, _ in required_docs:
            files = request.files.getlist(f'{key}[]')
            for fs in files:
                if not fs or not fs.filename:
                    continue
                if not _allowed_doc(fs.filename):
                    flash('نوع الملف غير مدعوم. المسموح: صور أو PDF', 'danger')
                    return render_template('client/upload_docs.html', request_obj=vr, required_docs=required_docs, max_bytes=current_app.config.get('MAX_CONTENT_LENGTH', 5*1024*1024))

                safe_name = secure_filename(fs.filename)
                ts = int(time.time())
                filename = f"{key}_{ts}_{safe_name}"
                # object key in B2 bucket
                object_key = f"uploads/requests/req_{vr.id}/{filename}"
                stored = store_file_and_get_url(
                    fs,
                    key=object_key,
                    local_abs_dir=requests_root,
                    filename=filename,
                )

                rd = RequestDocument(
                    valuation_request_id=vr.id,
                    doc_type=key,
                    file_path=stored,
                    original_filename=safe_name,
                )
                db.session.add(rd)

        db.session.commit()
        flash('تم رفع المستندات بنجاح', 'success')
        return redirect(url_for('client.dashboard'))

    return render_template('client/upload_docs.html', request_obj=vr, required_docs=required_docs, max_bytes=current_app.config.get('MAX_CONTENT_LENGTH', 5*1024*1024))


# -------------------------------
# Client proposes visit appointment after valuation completed
# -------------------------------
@client_bp.route('/appointments/propose/<int:request_id>', methods=['GET', 'POST'])
@login_required
def propose_appointment(request_id: int):
    if current_user.role != 'client':
        return "غير مصرح لك بالوصول", 403

    vr = ValuationRequest.query.get_or_404(request_id)
    if vr.client_id != current_user.id:
        return "غير مصرح لك بالوصول", 403

    # Allow proposing only after client accepts the submitted valuation
    if (vr.status or '').lower() != 'approved':
        flash('يمكن تحديد موعد الزيارة بعد قبول التثمين من الشركة', 'warning')
        return redirect(url_for('client.dashboard'))

    if request.method == 'POST':
        proposed_raw = (request.form.get('proposed_time') or '').strip()
        notes = (request.form.get('notes') or '').strip() or None
        if not proposed_raw:
            flash('يرجى تحديد وقت الموعد', 'danger')
            return render_template('client/appointment_propose.html', request_obj=vr)
        try:
            # Expecting input type datetime-local => YYYY-MM-DDTHH:MM
            proposed_dt = datetime.fromisoformat(proposed_raw)
        except Exception:
            flash('تنسيق وقت غير صالح', 'danger')
            return render_template('client/appointment_propose.html', request_obj=vr)

        appt = VisitAppointment(
            valuation_request_id=vr.id,
            proposed_time=proposed_dt,
            proposed_by='client',
            status='pending',
            notes=notes,
        )
        db.session.add(appt)
        db.session.commit()
        flash('تم إرسال اقتراح موعد الزيارة إلى الشركة', 'success')
        return redirect(url_for('client.dashboard'))

    return render_template('client/appointment_propose.html', request_obj=vr)


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
