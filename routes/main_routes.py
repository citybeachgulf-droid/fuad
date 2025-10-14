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
    LandPrice,
    CompanyLandPrice,
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
# Static info pages
# -------------------------------
@main.route('/privacy')
def privacy():
    return render_template('legal/privacy.html')


@main.route('/terms')
def terms():
    return render_template('legal/terms.html')


@main.route('/support')
def support():
    return render_template('support.html')


# -------------------------------
# صفحة تجارب العملاء (عرض جميع التعليقات)
# -------------------------------
@main.route('/testimonials')
def testimonials_page():
    page = request.args.get('page', 1, type=int)
    per_page = 12
    pagination = (
        Testimonial.query
        .order_by(Testimonial.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return render_template(
        'testimonials.html',
        testimonials=pagination.items,
        pagination=pagination,
    )


# -------------------------------
# صفحات منفصلة للتقييم الفوري والمعتمد
# -------------------------------
@main.route('/quick')
def quick_page():
    """صفحة التقييم الفوري كوحدة مستقلة."""
    # إعادة توجيه مباشرة لصفحة الجدول/النتيجة
    return redirect(url_for('main.quick_step_summary'))


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
    # جعل القيم الافتراضية بسيطة، مع إمكانية تعديلها من الواجهة
    prop_type = request.args.get('prop_type') or 'land'
    # نحافظ على قيمة تقديرية ابتدائية ثابتة لإظهار أعلى البطاقة
    estimate = 50000
    # قائمة الشركات لعرضها في التقييم الفوري
    companies = User.query.filter_by(role='company').order_by(User.name.asc()).all()
    # اختيار مُسبق عبر الاستعلام (اختياري) + التحقق من وجود الشركة
    selected_company_id = None
    try:
        selected_company_id = int(request.args.get('company_id')) if request.args.get('company_id') else None
    except Exception:
        selected_company_id = None
    if selected_company_id is not None:
        exists = User.query.filter_by(id=selected_company_id, role='company').first()
        if not exists:
            selected_company_id = None
    return render_template(
        'quick/summary.html',
        estimate=estimate,
        prop_type=prop_type,
        loc=None,
        companies=companies,
        selected_company_id=selected_company_id,
    )


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
            {"title": "تثمين عقار قائم", "href": url_for('main.certified_property_inputs', entity=entity, purpose='تثمين عقار قائم'), "icon_class": "bi bi-house-check", "color_class": "tile-primary"},
            {"title": "تثمين أرض", "href": url_for('main.certified_property_inputs', entity=entity, purpose='تثمين أرض'), "icon_class": "bi bi-geo", "color_class": "tile-success"},
            {"title": "تثمين بناء عقار", "href": url_for('main.certified_property_inputs', entity=entity, purpose='تثمين بناء عقار'), "icon_class": "bi bi-tools", "color_class": "tile-warning"},
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
    options = []
    for b in banks:
        options.append({
            "title": (b.user.name if b.user else b.slug),
            "href": url_for('main.certified_step_amount', entity=entity, purpose=purpose, bank=b.slug),
            # return b.logo_path directly; template will pass through static_or_external
            "logo_src": (b.logo_path if b.logo_path else None),
        })
    return render_template('certified_steps/step_bank.html', options=options, entity=entity, purpose=purpose)


@main.route('/certified/step/amount')
def certified_step_amount():
    entity = request.args.get('entity', 'person')
    purpose = request.args.get('purpose', 'buy')
    bank_slug = request.args.get('bank')

    bank = BankProfile.query.filter_by(slug=bank_slug).first() if bank_slug else None

    # Generate amount ranges as requested:
    # - First card: 10k–100k
    # - Then: 100k–200k, 200k–300k, ... up to 900k–1,000k
    ranges = []
    ranges.append((10000, 100000))
    for start_amount in range(100000, 1000000, 100000):
        end_amount = start_amount + 100000
        ranges.append((start_amount, end_amount))

    options = []
    for min_amount, max_amount in ranges:
        title = f"{min_amount:,} – {max_amount:,}"
        # For filtering, use the upper bound as the required amount
        options.append({
            "title": title,
            "href": url_for('main.certified_companies', entity=entity, purpose=purpose, bank=bank_slug, amount=max_amount),
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


@main.route('/certified/companies')
def certified_companies():
    entity = request.args.get('entity', 'person')
    purpose = request.args.get('purpose', 'buy')
    bank_slug = request.args.get('bank')
    bank = BankProfile.query.filter_by(slug=bank_slug).first() if bank_slug else None

    amount_raw = request.args.get('amount')
    try:
        amount = float(amount_raw) if amount_raw not in (None, '') else None
    except Exception:
        amount = None

    companies = []
    if bank and amount is not None:
        q = (
            db.session.query(CompanyApprovedBank, CompanyProfile, User)
            .join(CompanyProfile, CompanyApprovedBank.company_profile_id == CompanyProfile.id)
            .join(User, CompanyProfile.user_id == User.id)
            .filter(CompanyApprovedBank.bank_user_id == bank.user_id)
        )

        for cab, profile, user in q.all():
            limit_value = cab.limit_value if cab.limit_value is not None else profile.limit_value
            if limit_value is None:
                continue
            try:
                limit_val = float(limit_value)
            except Exception:
                continue
            if limit_val >= float(amount):
                companies.append({
                    'id': user.id,
                    'name': user.name,
                    'logo_path': profile.logo_path if profile.logo_path else None,
                    'limit_value': limit_val,
                })

    companies.sort(key=lambda x: x.get('limit_value') or 0, reverse=True)

    return render_template(
        'certified_steps/companies.html',
        entity=entity,
        purpose=purpose,
        bank=bank,
        amount=amount,
        companies=companies,
    )


# -------------------------------
# Certified flow: Property inputs step (searchable fields)
# -------------------------------
@main.route('/certified/step/property-inputs')
def certified_property_inputs():
    """Show property inputs with searchable suggestions for bank, use, wilaya, region.

    This step is used for both "تثمين عقار قائم" and "تثمين بناء عقار" flows.
    """
    entity = request.args.get('entity', 'person')
    purpose = request.args.get('purpose', 'تثمين عقار قائم')
    return render_template('certified_steps/step_property_inputs.html', entity=entity, purpose=purpose)


@main.route('/certified/offers')
def certified_offers():
    """Compute and display valuation offers per company based on entered inputs.

    Accepted query params:
      - entity: person/company (optional)
      - purpose: one of Arabic labels (e.g., "تثمين عقار قائم"/"تثمين أرض"/"تثمين بناء عقار")
      - bank: bank slug (optional) to filter companies approved by bank
      - wilaya: str
      - region: str
      - use: str (Arabic label, e.g. سكني/تجاري/...)
      - land_area: float
      - build_area: float
      - build_age: float (years)
    """
    entity = request.args.get('entity', 'person')
    purpose = request.args.get('purpose', 'تثمين عقار قائم')
    bank_slug = request.args.get('bank')
    wilaya = (request.args.get('wilaya') or '').strip()
    region = (request.args.get('region') or '').strip()
    use_raw = (request.args.get('use') or '').strip()

    def to_float(val):
        try:
            return float(val) if val not in (None, '') else None
        except Exception:
            return None

    land_area = to_float(request.args.get('land_area')) or 0.0
    build_area = to_float(request.args.get('build_area')) or 0.0
    build_age = to_float(request.args.get('build_age')) or 0.0

    # Map Arabic purpose to internal property type
    def purpose_to_type(p: str) -> str:
        p = (p or '').strip()
        if p == 'تثمين أرض':
            return 'land'
        if p == 'تثمين بناء عقار':
            return 'house'
        # default for "تثمين عقار قائم" and others
        return 'property'

    prop_type = purpose_to_type(purpose)

    # Normalize use (support Arabic synonyms) -> one of: housing/commercial/industrial/agricultural
    def normalize_use(value: str):
        v = (value or '').strip().lower()
        if not v:
            return None
        mapping = {
            'housing': {'housing', 'residential', 'سكن', 'سكني', 'سكنية'},
            'commercial': {'commercial', 'تجاري', 'تجارية'},
            'industrial': {'industrial', 'صناعي', 'صناعية'},
            'agricultural': {'agricultural', 'agriculture', 'زراعي', 'زراعية'},
        }
        for key, vals in mapping.items():
            if v in vals:
                return key
        return None

    normalized_use = normalize_use(use_raw)

    # Helper to fetch land/build prices per company for given wilaya/region
    def company_pricing(company_profile_id: int):
        clp = None
        if company_profile_id and wilaya and region:
            clp = CompanyLandPrice.query.filter_by(
                company_profile_id=company_profile_id,
                wilaya=wilaya,
                region=region,
            ).first()
        lp = None
        if wilaya and region:
            lp = LandPrice.query.filter_by(wilaya=wilaya, region=region).first()

        def prices_map_from(obj):
            if not obj:
                return {}
            return {
                'housing': obj.price_housing,
                'commercial': obj.price_commercial,
                'industrial': obj.price_industrial,
                'agricultural': obj.price_agricultural,
            }

        def first_non_null_price(price_map: dict):
            for k in ('housing', 'commercial', 'industrial', 'agricultural'):
                if price_map.get(k) is not None:
                    return price_map.get(k)
            return None

        company_prices = prices_map_from(clp)
        public_prices = prices_map_from(lp)
        company_legacy = (clp.price_per_sqm if clp and clp.price_per_sqm is not None else (clp.price_per_meter if clp else None))
        public_legacy = (lp.price_per_sqm if lp and lp.price_per_sqm is not None else (lp.price_per_meter if lp else None))

        selected_land_price = None
        if normalized_use:
            selected_land_price = (
                (company_prices.get(normalized_use) if company_prices else None)
                or (public_prices.get(normalized_use) if public_prices else None)
                or company_legacy
                or public_legacy
            )
        if selected_land_price is None:
            selected_land_price = (
                first_non_null_price(company_prices)
                or company_legacy
                or first_non_null_price(public_prices)
                or public_legacy
            )

        build_price = 220.0  # OMR per m² baseline
        loc_factor = 1.0
        return (selected_land_price, build_price, loc_factor)

    # Fee model (simple tiered, estimated)
    def estimate_fee(total_value: float, ptype: str) -> float:
        if total_value is None:
            return 0.0
        # baseline tiers
        tiers = [
            (50000, 80.0),
            (100000, 120.0),
            (200000, 160.0),
            (float('inf'), 200.0),
        ]
        base_fee = 200.0
        for limit, fee in tiers:
            if total_value <= limit:
                base_fee = fee
                break
        # adjust by property type
        if ptype == 'land':
            base_fee -= 20.0
        elif ptype == 'house':
            base_fee += 20.0
        return max(40.0, base_fee)

    # Determine company set
    bank = BankProfile.query.filter_by(slug=bank_slug).first() if bank_slug else None

    companies_q = None
    companies = []
    if bank:
        q = (
            db.session.query(CompanyApprovedBank, CompanyProfile, User)
            .join(CompanyProfile, CompanyApprovedBank.company_profile_id == CompanyProfile.id)
            .join(User, CompanyProfile.user_id == User.id)
            .filter(CompanyApprovedBank.bank_user_id == bank.user_id)
        )
        for cab, profile, user in q.all():
            companies.append({
                'user_id': user.id,
                'name': user.name,
                'logo_path': profile.logo_path if profile.logo_path else None,
                'limit_value': (cab.limit_value if cab.limit_value is not None else profile.limit_value),
                'company_profile_id': profile.id,
            })
    else:
        # All companies
        q = (
            db.session.query(CompanyProfile, User)
            .join(User, CompanyProfile.user_id == User.id)
            .order_by(User.name.asc())
        )
        for profile, user in q.all():
            companies.append({
                'user_id': user.id,
                'name': user.name,
                'logo_path': profile.logo_path if profile.logo_path else None,
                'limit_value': profile.limit_value,
                'company_profile_id': profile.id,
            })

    offers = []
    for c in companies:
        land_price, build_price, loc_factor = company_pricing(c['company_profile_id'])
        land_price = float(land_price) if land_price is not None else None
        # Compute valuation
        land_val = (land_area * land_price) if (land_price is not None and land_area) else 0.0
        if prop_type == 'land':
            build_val = 0.0
            depreciation = 1.0
        else:
            depreciation = max(0.40, 1 - (build_age or 0) * 0.02)
            build_val = (build_area * build_price * depreciation) if build_area else 0.0
        total_val = (land_val + build_val) * (loc_factor or 1.0)
        fee_val = estimate_fee(total_val, prop_type)

        offers.append({
            'company_id': c['user_id'],
            'company_name': c['name'],
            'logo_path': c['logo_path'],
            'limit_value': (float(c['limit_value']) if c.get('limit_value') is not None else None),
            'estimated_value': float(total_val) if total_val is not None else None,
            'estimated_fee': float(fee_val),
        })

    # Sort by highest estimated value
    offers.sort(key=lambda o: o.get('estimated_value') or 0, reverse=True)

    return render_template(
        'certified_steps/offers.html',
        entity=entity,
        purpose=purpose,
        bank=bank,
        wilaya=wilaya,
        region=region,
        use=use_raw,
        land_area=land_area,
        build_area=build_area,
        build_age=build_age,
        prop_type=prop_type,
        offers=offers,
    )


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
            'logo_path': (b.logo_path if b.logo_path else None)
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
                'logo_path': profile.logo_path if profile.logo_path else None,
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


# -------------------------------
# APIs for quick valuation company selections
# -------------------------------
@main.route('/api/companies', methods=['GET'])
def api_companies():
    companies = User.query.filter_by(role='company').order_by(User.name.asc()).all()
    return jsonify([
        {
            'id': c.id,
            'name': c.name,
            'logo_path': (c.company_profile.logo_path if getattr(c, 'company_profile', None) and c.company_profile.logo_path else None),
        } for c in companies
    ])


@main.route('/api/company_region_price', methods=['GET'])
def api_company_region_price():
    """Return land/build prices for wilaya/region considering selected company.

    Query params:
      - company_id: int (optional)
      - wilaya: str (required)
      - region: str (required)
      - use: str (optional) one of: housing, commercial, industrial, agricultural
    """
    wilaya = request.args.get('wilaya')
    region = request.args.get('region')
    company_id = request.args.get('company_id', type=int)
    use_raw = request.args.get('use')

    if not wilaya or not region:
        return jsonify({'error': 'wilaya and region are required'}), 400

    # Normalize use parameter (support English and Arabic synonyms)
    def normalize_use(value: str):
        v = (value or '').strip().lower()
        if not v:
            return None
        mapping = {
            'housing': {'housing', 'residential', 'سكن', 'سكني', 'سكنية'},
            'commercial': {'commercial', 'تجاري', 'تجارية'},
            'industrial': {'industrial', 'صناعي', 'صناعية'},
            'agricultural': {'agricultural', 'agriculture', 'زراعي', 'زراعية'},
        }
        for key, vals in mapping.items():
            if v in vals:
                return key
        return None

    normalized_use = normalize_use(use_raw)

    # Helpers to extract per-use prices from a row
    def prices_map_from(obj):
        if not obj:
            return {}
        return {
            'housing': obj.price_housing,
            'commercial': obj.price_commercial,
            'industrial': obj.price_industrial,
            'agricultural': obj.price_agricultural,
        }

    def first_non_null_price(price_map: dict):
        for k in ('housing', 'commercial', 'industrial', 'agricultural'):
            if price_map.get(k) is not None:
                return price_map.get(k)
        return None

    # Fetch company-specific and public rows (for robust fallback by selected use)
    clp = None
    lp = None

    # Try company-specific first
    if company_id:
        company_profile = CompanyProfile.query.filter_by(user_id=company_id).first()
        if company_profile:
            clp = CompanyLandPrice.query.filter_by(
                company_profile_id=company_profile.id,
                wilaya=wilaya,
                region=region,
            ).first()
    # Always fetch public row as well for complete fallback
    lp = LandPrice.query.filter_by(wilaya=wilaya, region=region).first()

    company_prices = prices_map_from(clp)
    public_prices = prices_map_from(lp)
    company_legacy = (clp.price_per_sqm if clp and clp.price_per_sqm is not None else (clp.price_per_meter if clp else None))
    public_legacy = (lp.price_per_sqm if lp and lp.price_per_sqm is not None else (lp.price_per_meter if lp else None))

    # Selection logic prioritizes requested use across sources, then general fallbacks
    selected_land_price = None
    if normalized_use:
        selected_land_price = (
            (company_prices.get(normalized_use) if company_prices else None)
            or (public_prices.get(normalized_use) if public_prices else None)
            or company_legacy
            or public_legacy
        )
    if selected_land_price is None:
        selected_land_price = (
            first_non_null_price(company_prices)
            or company_legacy
            or first_non_null_price(public_prices)
            or public_legacy
        )

    # Defaults for build price and location factor if not modeled per company
    build_price = 220.0
    loc_factor = 1.0

    return jsonify({
        'landPrice': float(selected_land_price) if selected_land_price is not None else None,
        'buildPrice': float(build_price),
        'locFactor': float(loc_factor),
    })


@main.route('/api/land_locations', methods=['GET'])
def api_land_locations():
    """Return list of wilayas and their regions for quick valuation selectors.

    If a company_id is provided and that company has uploaded land prices,
    wilayas/regions are sourced from `CompanyLandPrice` for that company.
    Otherwise, they fall back to the public `LandPrice` table.

    Query params:
      - company_id: int (optional)

    Response shape:
      {
        "locations": [
          {"wilaya": "مسقط", "regions": ["السيب", "بوشر", ...]},
          ...
        ]
      }
    """
    company_id = request.args.get('company_id', type=int)

    # Build mapping wilaya -> set(regions)
    locations_map = {}

    if company_id:
        company_profile = CompanyProfile.query.filter_by(user_id=company_id).first()
        if company_profile:
            rows = (
                db.session.query(CompanyLandPrice.wilaya, CompanyLandPrice.region)
                .filter(CompanyLandPrice.company_profile_id == company_profile.id)
                .all()
            )
            for w, r in rows:
                if not w or not r:
                    continue
                locations_map.setdefault(w, set()).add(r)

    # Fallback to public land prices if no company-specific locations
    if not locations_map:
        rows = db.session.query(LandPrice.wilaya, LandPrice.region).all()
        for w, r in rows:
            if not w or not r:
                continue
            locations_map.setdefault(w, set()).add(r)

    # Convert to sorted lists
    locations = []
    for w in sorted(locations_map.keys()):
        regions_sorted = sorted(locations_map[w])
        locations.append({'wilaya': w, 'regions': regions_sorted})

    return jsonify({'locations': locations})
