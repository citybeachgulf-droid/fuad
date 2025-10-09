from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, User, InviteToken, News, Advertisement
from flask_login import login_required, current_user
from urllib.parse import urljoin
from flask import current_app
import os
from werkzeug.utils import secure_filename

admin_bp = Blueprint('admin', __name__, template_folder='../templates/admin', static_folder='../static')


# --- Dashboard (محمي ويعرض البنوك والشركات) ---
from models import ValuationRequest

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403

    banks = User.query.filter_by(role='bank').all()
    companies = User.query.filter_by(role='company').all()
    clients = User.query.filter_by(role='client').all()
    requests = ValuationRequest.query.all()

    latest_news = News.query.order_by(News.created_at.desc()).limit(3).all()

    return render_template(
        'dashboard.html',
        banks=banks,
        companies=companies,
        clients=clients,
        requests=requests,
        latest_news=latest_news
    )

# --- صفحة عرض طلبات التثمين ---
@admin_bp.route('/requests')
@login_required
def requests_list():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    requests = ValuationRequest.query.order_by(ValuationRequest.id.desc()).all()
    return render_template('requests.html', requests=requests)

# --- إضافة بنك ---
@admin_bp.route('/add_bank', methods=['POST'])
@login_required
def add_bank():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    name = request.form['name']
    email = request.form['email']
    phone = request.form.get('phone')
    # إنشاء دعوة
    invite = InviteToken.generate(email=email, role='bank', invited_by_id=current_user.id, name=name, phone=phone)
    # إنشاء رابط التسجيل
    base_url = (f"http://{current_app.config['SERVER_NAME']}/" if current_app.config.get('SERVER_NAME') else request.host_url)
    invite_url = urljoin(base_url, url_for('auth.register', token=invite.token))

    flash(f'تم إنشاء دعوة للبنك. رابط التسجيل: {invite_url}', 'success')
    return redirect(url_for('admin.dashboard'))

# --- إضافة شركة تثمين ---
@admin_bp.route('/add_company', methods=['POST'])
@login_required
def add_company():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    name = request.form['name']
    email = request.form['email']
    phone = request.form.get('phone')
    # إنشاء دعوة
    invite = InviteToken.generate(email=email, role='company', invited_by_id=current_user.id, name=name, phone=phone)
    # إنشاء رابط التسجيل
    base_url = (f"http://{current_app.config['SERVER_NAME']}/" if current_app.config.get('SERVER_NAME') else request.host_url)
    invite_url = urljoin(base_url, url_for('auth.register', token=invite.token))

    flash(f'تم إنشاء دعوة للشركة. رابط التسجيل: {invite_url}', 'success')
    return redirect(url_for('admin.dashboard'))

# --- صفحة عرض البنوك ---
@admin_bp.route('/banks')
@login_required
def banks():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    banks = User.query.filter_by(role='bank').all()
    return render_template('banks.html', banks=banks)

# --- صفحة عرض شركات التثمين ---
@admin_bp.route('/companies')
@login_required
def companies():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    companies = User.query.filter_by(role='company').all()
    return render_template('companies.html', companies=companies)

# --- صفحة عرض الدعوات ---
@admin_bp.route('/invites')
@login_required
def invites():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403

    invites_qs = InviteToken.query.order_by(InviteToken.created_at.desc()).all()

    base_url = (f"http://{current_app.config['SERVER_NAME']}/" if current_app.config.get('SERVER_NAME') else request.host_url)
    invites_data = []
    for inv in invites_qs:
        invite_url = urljoin(base_url, url_for('auth.register', token=inv.token))
        invites_data.append({
            'name': (inv.name or (inv.email.split('@')[0] if inv.email else '')),
            'email': inv.email,
            'role': inv.role,
            'url': invite_url,
            'used_at': inv.used_at,
            'expires_at': inv.expires_at,
        })

    return render_template('invites.html', invites=invites_data)


# --- إعداد رفع صور الأخبار ---
def _ensure_news_upload_dir(app):
    configured = app.config.get('NEWS_UPLOAD_FOLDER')
    if configured:
        news_upload = configured
    else:
        base_upload = app.config.get('UPLOAD_FOLDER', os.path.join(app.root_path, 'static', 'uploads'))
        news_upload = os.path.join(os.path.dirname(base_upload), 'news') if base_upload.endswith('logos') else os.path.join(base_upload, 'news')
    os.makedirs(news_upload, exist_ok=True)
    return news_upload


# --- قائمة الأخبار ---
@admin_bp.route('/news')
@login_required
def news_list():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    items = News.query.order_by(News.created_at.desc()).all()
    return render_template('news_list.html', news_list=items)


# --- إنشاء خبر جديد ---
@admin_bp.route('/news/new', methods=['GET', 'POST'])
@login_required
def news_new():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        body = request.form.get('body', '').strip()
        if not title:
            flash('الرجاء إدخال عنوان الخبر', 'danger')
            return redirect(url_for('admin.news_new'))

        image_path_rel = None
        file = request.files.get('image')
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_dir = _ensure_news_upload_dir(current_app)
            save_path = os.path.join(upload_dir, filename)
            # تجنب التعارض: أعد التسمية إذا كان الملف موجوداً
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(save_path):
                filename = f"{base}_{counter}{ext}"
                save_path = os.path.join(upload_dir, filename)
                counter += 1
            file.save(save_path)
            # المسار النسبي داخل static
            # نفترض أن مجلد news داخل static/uploads/news
            image_path_rel = f"uploads/news/{filename}"

        news = News(title=title, body=body, image_path=image_path_rel)
        db.session.add(news)
        db.session.commit()
        flash('تم إضافة الخبر بنجاح', 'success')
        return redirect(url_for('admin.news_list'))

    return render_template('news_form.html')


# --- إدارة الإعلانات ---
@admin_bp.route('/ads')
@login_required
def ads_list():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    items = Advertisement.query.order_by(Advertisement.placement.asc(), Advertisement.sort_order.asc(), Advertisement.created_at.desc()).all()
    return render_template('ads_list.html', ads=items)


@admin_bp.route('/ads/new', methods=['GET', 'POST'])
@login_required
def ads_new():
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403

    if request.method == 'POST':
        title = (request.form.get('title') or '').strip()
        target_url = (request.form.get('target_url') or '').strip()
        placement = (request.form.get('placement') or 'homepage_top').strip()
        sort_order_raw = (request.form.get('sort_order') or '0').strip()
        is_active = (request.form.get('is_active') == 'on')
        start_at = request.form.get('start_at') or None
        end_at = request.form.get('end_at') or None

        # Parse datetimes if provided
        from datetime import datetime
        fmt = '%Y-%m-%dT%H:%M'
        start_dt = datetime.strptime(start_at, fmt) if start_at else None
        end_dt = datetime.strptime(end_at, fmt) if end_at else None

        image_path_rel = None
        file = request.files.get('image')
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_dir = _ensure_ads_upload_dir(current_app)
            save_path = os.path.join(upload_dir, filename)
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(save_path):
                filename = f"{base}_{counter}{ext}"
                save_path = os.path.join(upload_dir, filename)
                counter += 1
            file.save(save_path)
            image_path_rel = f"uploads/ads/{filename}"

        try:
            sort_order = int(sort_order_raw)
        except Exception:
            sort_order = 0

        if not image_path_rel:
            flash('الرجاء رفع صورة للإعلان', 'danger')
            return redirect(url_for('admin.ads_new'))

        ad = Advertisement(
            title=title or None,
            image_path=image_path_rel,
            target_url=target_url or None,
            placement=placement or 'homepage_top',
            sort_order=sort_order,
            is_active=is_active,
            start_at=start_dt,
            end_at=end_dt,
        )
        db.session.add(ad)
        db.session.commit()
        flash('تم إنشاء الإعلان بنجاح', 'success')
        return redirect(url_for('admin.ads_list'))

    return render_template('ads_form.html')


@admin_bp.route('/ads/<int:ad_id>/toggle', methods=['POST'])
@login_required
def ads_toggle(ad_id: int):
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    ad = Advertisement.query.get_or_404(ad_id)
    ad.is_active = not ad.is_active
    db.session.commit()
    flash('تم تحديث حالة الإعلان', 'success')
    return redirect(url_for('admin.ads_list'))


@admin_bp.route('/ads/<int:ad_id>/delete', methods=['POST'])
@login_required
def ads_delete(ad_id: int):
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403
    ad = Advertisement.query.get_or_404(ad_id)
    db.session.delete(ad)
    db.session.commit()
    flash('تم حذف الإعلان', 'success')
    return redirect(url_for('admin.ads_list'))


def _ensure_ads_upload_dir(app):
    configured = app.config.get('ADS_UPLOAD_FOLDER')
    if configured:
        ads_upload = configured
    else:
        base_upload = app.config.get('UPLOAD_FOLDER', os.path.join(app.root_path, 'static', 'uploads'))
        ads_upload = os.path.join(os.path.dirname(base_upload), 'ads') if base_upload.endswith('logos') else os.path.join(base_upload, 'ads')
    os.makedirs(ads_upload, exist_ok=True)
    return ads_upload


# --- تحديث بيانات بنك (المدير فقط) ---
@admin_bp.route('/banks/<int:bank_id>/update', methods=['POST'])
@login_required
def update_bank(bank_id: int):
    if current_user.role != 'admin':
        return "غير مصرح لك بالوصول", 403

    bank_user = User.query.filter_by(id=bank_id, role='bank').first_or_404()

    name = (request.form.get('name') or '').strip()
    email = (request.form.get('email') or '').strip()
    phone = (request.form.get('phone') or '').strip()
    password = request.form.get('password') or ''

    # التحقق من البريد الإلكتروني الفريد إذا تم تغييره
    if email and email != bank_user.email:
        if User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني مستخدم من قبل.', 'danger')
            return redirect(url_for('admin.banks'))

    if name:
        bank_user.name = name
    if email:
        bank_user.email = email
    if phone:
        bank_user.phone = phone
    else:
        # السماح بتفريغ الهاتف
        bank_user.phone = None

    if password:
        bank_user.set_password(password)

    db.session.commit()
    flash('تم تحديث بيانات البنك بنجاح', 'success')
    return redirect(url_for('admin.banks'))
