from flask import Blueprint, render_template, abort, request, jsonify, url_for, redirect
from models import (
    db,
    User,
    CompanyProfile,
    News,
    BankProfile,
    BankOffer,
    CompanyApprovedBank,
    Advertisement,
    Testimonial,
)

main = Blueprint('main', __name__)

@main.route('/')
def landing():
    latest_news = News.query.order_by(News.created_at.desc()).limit(3).all()
    # Fetch active ads for homepage top
    ads_qs = Advertisement.query.filter_by(placement='homepage_top').order_by(Advertisement.sort_order.asc(), Advertisement.created_at.desc()).all()
    active_ads = [ad for ad in ads_qs if ad.is_currently_visible()]
    testimonials = Testimonial.query.order_by(Testimonial.created_at.desc()).limit(6).all()
    return render_template('landing.html', latest_news=latest_news, ads_top=active_ads, testimonials=testimonials)


# -------------------------------
# صفحات منفصلة للتقييم الفوري والمعتمد
# -------------------------------
@main.route('/quick')
def quick_page():
    """صفحة التقييم الفوري كوحدة مستقلة."""
    # إعادة توجيه إلى الخطوة الأولى بنمط البطاقات
    return redirect(url_for('main.quick_step_property'))


@main.route('/certified')
def certified_page():
    """صفحة التقييم المعتمد كوحدة مستقلة."""
    # إعادة توجيه إلى الخطوة الأولى بنمط البطاقات
    return redirect(url_for('main.certified_step_entity'))


# -------------------------------
# Quick flow (cards only)
# -------------------------------
@main.route('/quick/step/property')
def quick_step_property():
    options = [
        {"title": "أرض فقط", "href": url_for('main.quick_step_location', prop_type='land'), "icon_class": "bi bi-geo", "color_class": "tile-primary", "subtitle": "قطعة أرض بدون بناء"},
        {"title": "منزل/فيلا", "href": url_for('main.quick_step_location', prop_type='house'), "icon_class": "bi bi-house", "color_class": "tile-success", "subtitle": "سكني مكتمل أو قيد البناء"},
        {"title": "شقة", "href": url_for('main.quick_step_location', prop_type='apartment'), "icon_class": "bi bi-building", "color_class": "tile-warning", "subtitle": "وحدة سكنية في مبنى"},
    ]
    return render_template('quick/step_property.html', options=options)


@main.route('/quick/step/location')
def quick_step_location():
    prop_type = request.args.get('prop_type', 'land')
    locations = [
        {"title": "منطقة أ", "href": url_for('main.quick_step_summary', prop_type=prop_type, loc='A'), "icon_class": "bi bi-geo-alt", "color_class": "tile-primary"},
        {"title": "منطقة ب", "href": url_for('main.quick_step_summary', prop_type=prop_type, loc='B'), "icon_class": "bi bi-geo-alt", "color_class": "tile-success"},
        {"title": "منطقة ج", "href": url_for('main.quick_step_summary', prop_type=prop_type, loc='C'), "icon_class": "bi bi-geo-alt", "color_class": "tile-warning"},
    ]
    return render_template('quick/step_location.html', options=locations)


@main.route('/quick/summary')
def quick_step_summary():
    # عرض نتيجة تقديرية بسيطة وفق الاختيارات
    prop_type = request.args.get('prop_type', 'land')
    loc = request.args.get('loc', 'A')
    base_values = {'land': 20000, 'house': 80000, 'apartment': 50000}
    loc_factor = {'A': 1.3, 'B': 1.0, 'C': 0.8}
    estimate = int(base_values.get(prop_type, 30000) * loc_factor.get(loc, 1))
    return render_template('quick/summary.html', estimate=estimate, prop_type=prop_type, loc=loc)


# -------------------------------
# Certified flow (cards only)
# -------------------------------
@main.route('/certified/step/entity')
def certified_step_entity():
    options = [
        {"title": "فرد", "href": url_for('main.certified_step_purpose', entity='person'), "icon_class": "bi bi-person-fill", "color_class": "tile-primary", "subtitle": "خيارات التمويل للأفراد"},
        {"title": "شركة", "href": url_for('main.certified_step_purpose', entity='company'), "icon_class": "bi bi-buildings", "color_class": "tile-success", "subtitle": "خدمات التمويل للشركات"},
    ]
    return render_template('certified_steps/step_entity.html', options=options)


@main.route('/certified/step/purpose')
def certified_step_purpose():
    entity = request.args.get('entity', 'person')
    if entity == 'person':
        options = [
            {"title": "شراء جديد", "href": url_for('main.certified_step_bank', entity=entity, purpose='buy'), "icon_class": "bi bi-bag-plus", "color_class": "tile-warning"},
            {"title": "فك رهن", "href": url_for('main.certified_step_bank', entity=entity, purpose='release'), "icon_class": "bi bi-unlock", "color_class": "tile-warning"},
            {"title": "نقل مديونية", "href": url_for('main.certified_step_bank', entity=entity, purpose='transfer'), "icon_class": "bi bi-arrow-left-right", "color_class": "tile-warning"},
        ]
    else:
        options = [
            {"title": "بيع", "href": url_for('main.certified_step_bank', entity=entity, purpose='sell'), "icon_class": "bi bi-cash-coin", "color_class": "tile-warning"},
            {"title": "شراء", "href": url_for('main.certified_step_bank', entity=entity, purpose='buy'), "icon_class": "bi bi-bag", "color_class": "tile-warning"},
            {"title": "تقارير مالية", "href": url_for('main.certified_step_bank', entity=entity, purpose='reports'), "icon_class": "bi bi-clipboard-data", "color_class": "tile-warning"},
            {"title": "إعادة تمويل", "href": url_for('main.certified_step_bank', entity=entity, purpose='refinance'), "icon_class": "bi bi-arrow-repeat", "color_class": "tile-warning"},
        ]
    return render_template('certified_steps/step_purpose.html', options=options, entity=entity)


@main.route('/certified/step/bank')
def certified_step_bank():
    entity = request.args.get('entity', 'person')
    purpose = request.args.get('purpose', 'buy')
    banks = BankProfile.query.order_by(BankProfile.id.asc()).all()
    options = [
        {"title": (b.user.name if b.user else b.slug), "href": url_for('main.certified_step_amount', entity=entity, purpose=purpose, bank=b.slug), "icon_class": "bi bi-bank", "color_class": "tile-primary", "subtitle": (b.website or '')}
        for b in banks
    ]
    return render_template('certified_steps/step_bank.html', options=options, entity=entity, purpose=purpose)


@main.route('/certified/step/amount')
def certified_step_amount():
    entity = request.args.get('entity', 'person')
    purpose = request.args.get('purpose', 'buy')
    bank_slug = request.args.get('bank')

    bank = BankProfile.query.filter_by(slug=bank_slug).first() if bank_slug else None

    # Generate amounts from 10k to 100k (step 10k)
    amounts = list(range(10000, 100001, 10000))
    options = []
    for amt in amounts:
        options.append({
            "title": f"{amt:,}",
            "href": url_for('main.certified_summary', entity=entity, purpose=purpose, bank=bank_slug, amount=amt),
            "icon_class": "bi bi-cash-stack",
            "color_class": "tile-success",
            "subtitle": "ريال"
        })

    return render_template('certified_steps/step_amount.html', options=options, entity=entity, purpose=purpose, bank=bank)


@main.route('/certified/summary')
def certified_summary():
    entity = request.args.get('entity', 'person')
    purpose = request.args.get('purpose', 'buy')
    bank_slug = request.args.get('bank')
    bank = BankProfile.query.filter_by(slug=bank_slug).first() if bank_slug else None
    amount_raw = request.args.get('amount')
    try:
        amount = int(amount_raw) if amount_raw not in (None, '') else None
    except Exception:
        amount = None
    return render_template('certified_steps/summary.html', entity=entity, purpose=purpose, bank=bank, amount=amount)


@main.route('/companies')
def companies_list():
    companies = User.query.filter_by(role='company').all()
    return render_template('companies/list.html', companies=companies)


@main.route('/companies/<int:company_id>')
def company_detail(company_id: int):
    company = User.query.filter_by(id=company_id, role='company').first()
    if not company:
        return abort(404)
    return render_template('companies/detail.html', company=company)


# -------------------------------
# البنوك: قائمة + صفحة تفاصيل بنك
# -------------------------------
@main.route('/banks')
def banks_list():
    banks = BankProfile.query.order_by(BankProfile.id.asc()).all()
    return render_template('banks/list.html', banks=banks)


@main.route('/banks/<string:slug>')
def bank_detail(slug: str):
    bank = BankProfile.query.filter_by(slug=slug).first()
    if not bank:
        return abort(404)
    # تمرير عروض البنك للواجهة لعرضها مع الحاسبة
    return render_template('banks/detail.html', bank=bank, offers=bank.offers)


# -------------------------------
# صفحة حاسبة القروض العامة
# تعتمد على سياسات وعروض البنوك
# -------------------------------
@main.route('/calculator')
def calculator():
    # نجلب جميع العروض مع معلومات البنك لعرضها في القائمة المنسدلة
    offers = (
        BankOffer.query
        .join(BankProfile, BankOffer.bank_profile_id == BankProfile.id)
        .order_by(BankProfile.id.asc(), BankOffer.product_name.asc())
        .all()
    )
    return render_template('calculator.html', offers=offers)


# -------------------------------
# APIs for landing page filtering
# -------------------------------
@main.route('/api/banks', methods=['GET'])
def api_list_banks():
    banks = BankProfile.query.order_by(BankProfile.id.asc()).all()
    return jsonify([
        {
            'slug': b.slug,
            'name': b.user.name if b.user else b.slug,
            'logo_path': (f"/static/{b.logo_path}" if b.logo_path else None)
        } for b in banks
    ])


@main.route('/api/certified_companies', methods=['GET'])
def api_certified_companies():
    """Return companies approved by the given bank and with sufficient limit.

    Query params:
      - bank_slug: str (required)
      - amount: float (required)
    """
    bank_slug = request.args.get('bank_slug')
    amount_raw = request.args.get('amount')
    try:
        amount = float(amount_raw) if amount_raw not in (None, '') else None
    except Exception:
        amount = None

    if not bank_slug or amount is None:
        return jsonify({'error': 'bank_slug and amount are required'}), 400

    bank = BankProfile.query.filter_by(slug=bank_slug).first()
    if not bank:
        return jsonify({'error': 'bank not found'}), 404

    # Join CompanyApprovedBank -> CompanyProfile -> User
    q = (
        db.session.query(CompanyApprovedBank, CompanyProfile, User)
        .join(CompanyProfile, CompanyApprovedBank.company_profile_id == CompanyProfile.id)
        .join(User, CompanyProfile.user_id == User.id)
        .filter(CompanyApprovedBank.bank_user_id == bank.user_id)
    )

    results = []
    for cab, profile, user in q.all():
        limit_value = cab.limit_value if cab.limit_value is not None else profile.limit_value
        if limit_value is None:
            continue
        if float(limit_value) >= float(amount):
            results.append({
                'id': user.id,
                'name': user.name,
                'logo_path': f"/static/{profile.logo_path}" if profile.logo_path else None,
                'limit_value': float(limit_value),
            })

    return jsonify(results)


# -------------------------------
# Testimonials API (list + create)
# -------------------------------
@main.route('/api/testimonials', methods=['GET'])
def api_testimonials_list():
    try:
        limit_raw = request.args.get('limit')
        limit = int(limit_raw) if limit_raw else 10
    except Exception:
        limit = 10

    qs = (
        Testimonial.query
        .order_by(Testimonial.created_at.desc())
        .limit(limit)
        .all()
    )
    def serialize(t: Testimonial):
        return {
            'id': t.id,
            'name': t.name,
            'property_type': t.property_type,
            'rating': t.rating,
            'body': t.body,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        }
    return jsonify([serialize(t) for t in qs])


@main.route('/api/testimonials', methods=['POST'])
def api_testimonials_create():
    # Accept JSON or form-encoded payloads
    payload = request.get_json(silent=True) or request.form

    name = (payload.get('name') or '').strip()
    body = (payload.get('body') or payload.get('experience') or '').strip()
    property_type = (payload.get('property_type') or '').strip() or None

    rating_val = payload.get('rating')
    rating = None
    if rating_val not in (None, ''):
        try:
            rating = int(rating_val)
        except Exception:
            rating = None
    if rating is not None:
        if rating < 1:
            rating = 1
        if rating > 5:
            rating = 5

    if not name or not body:
        return jsonify({'error': 'name and body are required'}), 400

    t = Testimonial(name=name, body=body, property_type=property_type, rating=rating)
    db.session.add(t)
    db.session.commit()

    return jsonify({
        'id': t.id,
        'name': t.name,
        'property_type': t.property_type,
        'rating': t.rating,
        'body': t.body,
        'created_at': t.created_at.isoformat() if t.created_at else None,
    }), 201
