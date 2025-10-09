from flask import Blueprint, render_template, abort, request, jsonify
from models import db, User, CompanyProfile, News, BankProfile, BankOffer, CompanyApprovedBank

main = Blueprint('main', __name__)

@main.route('/')
def landing():
    latest_news = News.query.order_by(News.created_at.desc()).limit(3).all()
    return render_template('landing.html', latest_news=latest_news)


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
