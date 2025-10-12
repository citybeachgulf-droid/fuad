from flask import Flask, render_template, redirect, url_for, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
import os
from flask_login import LoginManager, current_user, login_required
from models import db, User, ValuationRequest, BankProfile, BankOffer
from sqlalchemy import inspect, text
from authlib.integrations.flask_client import OAuth  # ✅ ضروري
from config import Config
from dotenv import load_dotenv

# Optional Backblaze B2 native SDK (we'll fallback gracefully if unavailable)
try:  # pragma: no cover - optional dependency
    from b2sdk.v1 import InMemoryAccountInfo, B2Api  # type: ignore
    _HAS_B2SDK = True
except Exception:  # pragma: no cover
    InMemoryAccountInfo = None  # type: ignore
    B2Api = None  # type: ignore
    _HAS_B2SDK = False
# Blueprints
from routes.auth_routes import auth
from routes.admin_routes import admin_bp
from routes.company_routes import company_bp
from routes.bank_routes import bank_bp
from routes.client_routes import client_bp
from routes.main_routes import main
from routes.conversation_routes import conversations_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    # Respect proxy headers
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    db.init_app(app)

    # Arabic labels for request document types and Jinja filter
    DOC_TYPE_LABELS_AR = {
        "ids": "بطاقات هوية",
        "kroki": "كروكي",
        "deed": "صك الملكية",
        "completion_certificate": "شهادة إتمام البناء",
        "maps": "خرائط",
        "contractor_agreement": "اتفاقية المقاول",
    }

    @app.template_filter('doc_label_ar')
    def doc_label_ar(doc_type: str) -> str:
        key = str(doc_type or "").strip()
        return DOC_TYPE_LABELS_AR.get(key, key)

    @app.template_filter('static_or_external')
    def static_or_external(path: str) -> str:
        """Return a fully-qualified URL for either an external URL or a static asset.

        - If the provided path is an absolute URL (http/https), return as-is.
        - Otherwise, treat it as a path relative to the Flask 'static' folder.
        """
        try:
            p = (path or '').strip()
            if p.lower().startswith('http://') or p.lower().startswith('https://'):
                return p
            return url_for('static', filename=p)
        except Exception:
            return '#'

    # إعداد OAuth
    oauth = OAuth(app)
    google = oauth.register(
        name='google',
        client_id='35722269243-fdj189u3r1n05rnsmp6q2vjcdhs4vcui.apps.googleusercontent.com',
        client_secret='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',
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'}
    )

    # Ensure upload folders exist
    os.makedirs(app.config.get('UPLOAD_FOLDER', ''), exist_ok=True)
    os.makedirs(app.config.get('NEWS_UPLOAD_FOLDER', ''), exist_ok=True)
    os.makedirs(app.config.get('ADS_UPLOAD_FOLDER', ''), exist_ok=True)

    # إعداد LoginManager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    app.register_blueprint(auth)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(company_bp, url_prefix='/company')
    app.register_blueprint(bank_bp, url_prefix='/bank')
    app.register_blueprint(client_bp, url_prefix='/client')
    app.register_blueprint(main)
    app.register_blueprint(conversations_bp)

    # -------------------- Backblaze B2 Integration --------------------
    load_dotenv()
    B2_KEY_ID = os.getenv("B2_KEY_ID")
    B2_APP_KEY = os.getenv("B2_APP_KEY")
    B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")

    # Map classic env vars to S3-compatible settings if not set
    if B2_KEY_ID and B2_APP_KEY and B2_BUCKET_NAME:
        app.config.setdefault('B2_S3_ACCESS_KEY_ID', app.config.get('B2_S3_ACCESS_KEY_ID') or B2_KEY_ID)
        app.config.setdefault('B2_S3_SECRET_ACCESS_KEY', app.config.get('B2_S3_SECRET_ACCESS_KEY') or B2_APP_KEY)
        app.config.setdefault('B2_S3_BUCKET', app.config.get('B2_S3_BUCKET') or B2_BUCKET_NAME)
        # Default to US-West endpoint if not provided; SDK path still works if wrong
        app.config.setdefault('B2_S3_ENDPOINT', app.config.get('B2_S3_ENDPOINT') or 'https://s3.us-west-002.backblazeb2.com')

    # Initialize native B2 SDK if available and credentials provided
    bucket = None
    if _HAS_B2SDK and B2_KEY_ID and B2_APP_KEY and B2_BUCKET_NAME:
        try:
            info = InMemoryAccountInfo()  # type: ignore
            b2_api = B2Api(info)  # type: ignore
            b2_api.authorize_account("production", B2_KEY_ID, B2_APP_KEY)
            bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
            # Derive download base URL for building public links when needed
            download_base = None
            try:
                # Try common attribute locations across b2sdk versions
                download_base = getattr(getattr(b2_api, 'session', None), 'download_url', None)
                if not download_base and hasattr(info, 'get_download_url'):
                    download_base = info.get_download_url()  # type: ignore[attr-defined]
            except Exception:
                download_base = None
            if download_base:
                # e.g., https://f002.backblazeb2.com
                app.b2_download_url_base = str(download_base)
                # If a public base isn't configured, set a reasonable default including /file/<bucket>
                app.config.setdefault('B2_PUBLIC_URL_BASE', f"{str(download_base).rstrip('/')}/file/{B2_BUCKET_NAME}")
        except Exception:
            bucket = None

    # Expose bucket on app for utils fallback
    app.b2_bucket = bucket  # may be None if not configured

    @app.route('/upload', methods=['POST'])
    @login_required
    def upload_file():
        """رفع الملفات إلى التخزين (Backblaze B2 إذا مُتاح)"""
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"error": "No file provided"}), 400
        # Use the shared storage helper to unify logic
        from utils import store_file_and_get_url
        # Save under uploads/misc
        safe_name = file.filename
        uploads_root = os.path.join(app.root_path, 'static', 'uploads', 'misc')
        object_key = f"uploads/misc/{safe_name}"
        url_or_path = store_file_and_get_url(
            file,
            key=object_key,
            local_abs_dir=uploads_root,
            filename=safe_name,
        )
        return jsonify({"message": "Uploaded successfully", "path": url_or_path})

    # -------------------- Health Check --------------------
    @app.route('/health')
    def health():
        return {"status": "ok"}

    @app.route('/dashboard')
    @login_required
    def dashboard():
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'company':
            return redirect(url_for('company.dashboard'))
        elif current_user.role == 'bank':
            return redirect(url_for('bank.dashboard'))
        else:
            return redirect(url_for('main.landing'))

    # ✅ نرجع الكائنات المهمة لاستخدامها في باقي الملفات
    app.oauth = oauth
    app.google = google
    app.b2_bucket = bucket  # لإعادة استخدامه في Blueprints الأخرى

    return app


app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # ----------------------------------------
        # تحديث الجداول الموجودة كما في الكود الأصلي
        # (لا يتم المساس بأي عملية حالية)
        # ----------------------------------------
        try:
            inspector = inspect(db.engine)
            cols = [c['name'] for c in inspector.get_columns('company_approved_banks')]
            if 'limit_value' not in cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE company_approved_banks ADD COLUMN limit_value FLOAT'))

            user_cols = [c['name'] for c in inspector.get_columns('users')]
            with db.engine.connect() as conn:
                if 'oauth_provider' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(50)"))
                if 'oauth_subject' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN oauth_subject VARCHAR(255)"))
                if 'email_verified' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0 NOT NULL"))

            ads_cols = [c['name'] for c in inspector.get_columns('advertisements')]
            if 'stored_in_utc' not in ads_cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE advertisements ADD COLUMN stored_in_utc BOOLEAN DEFAULT 0 NOT NULL'))

            vr_cols = [c['name'] for c in inspector.get_columns('valuation_requests')]
            if 'valuation_type' not in vr_cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE valuation_requests ADD COLUMN valuation_type VARCHAR(50)'))
            if 'requested_amount' not in vr_cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE valuation_requests ADD COLUMN requested_amount FLOAT'))
            if 'rejection_reason' not in vr_cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE valuation_requests ADD COLUMN rejection_reason TEXT'))
            if 'rejected_at' not in vr_cols:
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE valuation_requests ADD COLUMN rejected_at DATETIME'))

            # Land prices
            land_cols = [c['name'] for c in inspector.get_columns('land_prices')]
            with db.engine.connect() as conn:
                for col in ['wilaya','created_at','price_housing','price_commercial','price_industrial','price_agricultural','price_per_sqm','price_per_meter']:
                    if col not in land_cols:
                        conn.execute(text(f'ALTER TABLE land_prices ADD COLUMN {col} FLOAT'))

            company_land_cols = [c['name'] for c in inspector.get_columns('company_land_prices')]
            with db.engine.connect() as conn:
                for col in ['created_at','price_housing','price_commercial','price_industrial','price_agricultural','price_per_sqm','price_per_meter']:
                    if col not in company_land_cols:
                        conn.execute(text(f'ALTER TABLE company_land_prices ADD COLUMN {col} FLOAT'))
        except Exception:
            pass

        # إنشاء مدير النظام إذا لم يوجد
        if User.query.filter_by(role='admin').count() == 0:
            admin_user = User(name="مدير النظام", email="admin@platform.com", role="admin")
            admin_user.set_password("123")
            db.session.add(admin_user)
            db.session.commit()

        # Seed البنوك العمانية كما في الكود الأصلي
        def seed_omani_banks():
            banks = [
                {"name": "Bank Muscat", "slug": "bank-muscat", "website": "https://www.bankmuscat.com/"},
                {"name": "Bank Dhofar", "slug": "bank-dhofar", "website": "https://www.bankdhofar.com/"},
                {"name": "Sohar International", "slug": "sohar-international", "website": "https://soharinternational.com/"},
                {"name": "National Bank of Oman", "slug": "nbo", "website": "https://www.nbo.om/"},
                {"name": "Oman Arab Bank", "slug": "oman-arab-bank", "website": "https://www.oman-arabbank.com/"},
                {"name": "Ahli Bank", "slug": "ahli-bank", "website": "https://ahlibank.om/"},
                {"name": "HSBC Oman", "slug": "hsbc-oman", "website": "https://www.hsbc.co.om/"},
                {"name": "Bank Nizwa", "slug": "bank-nizwa", "website": "https://www.banknizwa.om/"},
                {"name": "Alizz Islamic Bank", "slug": "alizz-islamic-bank", "website": "https://alizzib.com/"},
            ]

            if BankProfile.query.count() > 0:
                return

            for b in banks:
                email = f"{b['slug']}@banks.om"
                existing_user = User.query.filter_by(email=email).first()
                if not existing_user:
                    u = User(name=b["name"], email=email, role="bank")
                    u.set_password("123")
                    db.session.add(u)
                    db.session.flush()
                else:
                    u = existing_user

                profile = BankProfile(
                    user_id=u.id,
                    slug=b["slug"],
                    website=b.get("website"),
                    about=f"عروض تمويل من {b['name']}"
                )
                db.session.add(profile)
                db.session.flush()

                offer = BankOffer(
                    bank_profile_id=profile.id,
                    product_name="قرض سكني",
                    rate_type="ثابت",
                    interest_rate=5.75,
                    min_amount=10000,
                    max_amount=300000,
                    min_tenure_months=12,
                    max_tenure_months=300,
                    notes="عرض توضيحي"
                )
                db.session.add(offer)

            db.session.commit()

        seed_omani_banks()

    app.run(host='0.0.0.0', port=5000, debug=True)
